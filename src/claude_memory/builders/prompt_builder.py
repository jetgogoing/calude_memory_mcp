"""
Claude记忆管理MCP服务 - PromptBuilder模块

将召回的记忆片段按优先级、主题和token预算拼接成Claude可理解的上下文。
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog
from pydantic import BaseModel, Field

from ..models.data_models import MemoryUnitModel
from ..utils.token_counter import TokenCounter

logger = structlog.get_logger()


class BuilderConfig(BaseModel):
    """构建器配置"""
    
    enable_deduplication: bool = Field(default=True, description="是否去重")
    # v1.4: 移除Quick-MU，简化优先级权重
    priority_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "global_mu": 1.5,
            "conversation": 1.0,
            "error_log": 1.3,
            "decision": 1.4,
            "archive": 1.1
        },
        description="优先级权重（v1.4已移除quick_mu）"
    )
    context_prefix: str = Field(
        default="以下是相关的历史上下文信息：\n\n",
        description="上下文前缀"
    )
    context_suffix: str = Field(
        default="\n\n基于以上历史信息，请回答用户的问题。",
        description="上下文后缀"
    )
    group_by_type: bool = Field(default=True, description="是否按类型分组")
    max_fragments_per_type: int = Field(default=5, description="每种类型最大片段数")


class BuiltPrompt(BaseModel):
    """构建后的提示"""
    
    content: str = Field(description="提示内容")
    token_count: int = Field(description="Token数量")
    fragment_count: int = Field(description="片段数量")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class PromptBuilder:
    """提示构建器"""
    
    def __init__(self, config: BuilderConfig):
        self.config = config
        self.token_counter = TokenCounter()
        self._seen_hashes: Set[str] = set()
        
        logger.info(
            "prompt_builder_initialized",
            deduplication=config.enable_deduplication,
            group_by_type=config.group_by_type
        )
    
    def build(
        self,
        memory_units: List[MemoryUnitModel],
        query: str,
        max_tokens: Optional[int] = None,
        fused_content: Optional[str] = None
    ) -> BuiltPrompt:
        """
        构建提示
        
        Args:
            memory_units: 记忆单元列表
            query: 用户查询
            max_tokens: 最大token限制
            fused_content: 融合后的内容（如果有）
            
        Returns:
            构建后的提示
        """
        # 重置去重集合
        self._seen_hashes.clear()
        
        # 如果有融合内容，优先使用
        if fused_content:
            return self._build_with_fused_content(fused_content, query)
        
        # 否则使用原始记忆单元构建
        return self._build_from_units(memory_units, query, max_tokens)
    
    def _build_with_fused_content(
        self,
        fused_content: str,
        query: str
    ) -> BuiltPrompt:
        """使用融合内容构建提示"""
        content = f"{self.config.context_prefix}{fused_content}{self.config.context_suffix}"
        token_count = self.token_counter.count_tokens(content)
        
        return BuiltPrompt(
            content=content,
            token_count=token_count,
            fragment_count=1,
            metadata={
                "query": query,
                "build_method": "fused",
                "has_prefix": True,
                "has_suffix": True
            }
        )
    
    def _build_from_units(
        self,
        memory_units: List[MemoryUnitModel],
        query: str,
        max_tokens: Optional[int] = None
    ) -> BuiltPrompt:
        """从记忆单元构建提示"""
        # 按优先级排序
        sorted_units = self._sort_by_priority(memory_units)
        
        # 去重
        if self.config.enable_deduplication:
            sorted_units = self._deduplicate_units(sorted_units)
        
        # 分组
        if self.config.group_by_type:
            grouped_units = self._group_by_type(sorted_units)
        else:
            grouped_units = {"all": sorted_units}
        
        # 构建内容
        content_parts = [self.config.context_prefix]
        fragment_count = 0
        current_tokens = self.token_counter.count_tokens(self.config.context_prefix)
        
        for unit_type, units in grouped_units.items():
            if self.config.group_by_type and unit_type != "all":
                type_header = f"\n## {self._get_type_header(unit_type)}\n\n"
                content_parts.append(type_header)
                current_tokens += self.token_counter.count_tokens(type_header)
            
            # 限制每种类型的片段数
            units_to_add = units[:self.config.max_fragments_per_type]
            
            for unit in units_to_add:
                unit_content = self._format_unit(unit)
                unit_tokens = self.token_counter.count_tokens(unit_content)
                
                # 检查token限制
                if max_tokens and current_tokens + unit_tokens > max_tokens:
                    break
                
                content_parts.append(unit_content)
                current_tokens += unit_tokens
                fragment_count += 1
        
        # 添加后缀
        suffix_tokens = self.token_counter.count_tokens(self.config.context_suffix)
        if not max_tokens or current_tokens + suffix_tokens <= max_tokens:
            content_parts.append(self.config.context_suffix)
            current_tokens += suffix_tokens
        
        content = "".join(content_parts)
        
        return BuiltPrompt(
            content=content,
            token_count=current_tokens,
            fragment_count=fragment_count,
            metadata={
                "query": query,
                "build_method": "units",
                "total_units": len(memory_units),
                "deduped_units": len(sorted_units),
                "grouped": self.config.group_by_type
            }
        )
    
    def _sort_by_priority(self, units: List[MemoryUnitModel]) -> List[MemoryUnitModel]:
        """按优先级排序"""
        def get_priority(unit: MemoryUnitModel) -> float:
            base_score = unit.relevance_score
            
            # 应用类型权重
            type_weight = self.config.priority_weights.get(
                unit.unit_type,
                1.0
            )
            
            # 考虑时间因素（越新越重要）
            # 这里简化处理，实际可以根据时间戳计算
            time_weight = 1.0
            
            return base_score * type_weight * time_weight
        
        return sorted(units, key=get_priority, reverse=True)
    
    def _deduplicate_units(self, units: List[MemoryUnitModel]) -> List[MemoryUnitModel]:
        """去重记忆单元"""
        deduped = []
        
        for unit in units:
            content_hash = self._hash_content(unit.content)
            
            if content_hash not in self._seen_hashes:
                self._seen_hashes.add(content_hash)
                deduped.append(unit)
            else:
                logger.debug(
                    "duplicate_unit_skipped",
                    unit_id=unit.memory_id,
                    hash=content_hash
                )
        
        return deduped
    
    def _hash_content(self, content: str) -> str:
        """计算内容哈希"""
        # 标准化内容（去除多余空白等）
        normalized = " ".join(content.split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _group_by_type(
        self,
        units: List[MemoryUnitModel]
    ) -> Dict[str, List[MemoryUnitModel]]:
        """按类型分组"""
        grouped = defaultdict(list)
        
        for unit in units:
            grouped[unit.unit_type].append(unit)
        
        return dict(grouped)
    
    def _get_type_header(self, unit_type: str) -> str:
        """获取类型标题 (v1.4: 移除Quick-MU)"""
        headers = {
            "global_mu": "全局记忆摘要",
            # v1.4: 移除quick_mu
            # "quick_mu": "近期记忆",
            "conversation": "对话历史",
            "error_log": "错误日志",
            "decision": "决策记录",
            "code_snippet": "代码片段",
            "documentation": "文档说明",
            "archive": "归档记忆"
        }
        
        return headers.get(unit_type, unit_type.replace("_", " ").title())
    
    def _format_unit(self, unit: MemoryUnitModel) -> str:
        """格式化记忆单元"""
        parts = []
        
        # 时间戳
        parts.append(f"[{unit.timestamp.strftime('%Y-%m-%d %H:%M')}]")
        
        # 相关性分数（调试用）
        if unit.relevance_score > 0:
            parts.append(f"(相关度: {unit.relevance_score:.2f})")
        
        # 内容
        parts.append(f"\n{unit.content}\n")
        
        # 分隔符
        parts.append("\n---\n")
        
        return " ".join(parts)
    
    def batch_build(
        self,
        unit_groups: List[Tuple[List[MemoryUnitModel], str]],
        max_tokens: Optional[int] = None
    ) -> List[BuiltPrompt]:
        """
        批量构建提示
        
        Args:
            unit_groups: (记忆单元列表, 查询)元组列表
            max_tokens: 最大token限制
            
        Returns:
            构建结果列表
        """
        results = []
        
        for units, query in unit_groups:
            try:
                built = self.build(units, query, max_tokens)
                results.append(built)
            except Exception as e:
                logger.error(
                    "batch_build_error",
                    query=query,
                    error=str(e)
                )
                # 返回空提示
                results.append(BuiltPrompt(
                    content="",
                    token_count=0,
                    fragment_count=0,
                    metadata={"error": str(e)}
                ))
        
        return results
    
    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        logger.info("builder_config_updated", updates=kwargs)