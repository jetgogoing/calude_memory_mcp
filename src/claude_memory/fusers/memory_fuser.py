"""
Claude记忆管理MCP服务 - MemoryFuser模块

使用轻量级模型将召回的记忆片段融合成结构化的背景上下文。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

from ..models.data_models import MemoryUnitModel
from ..utils.model_manager import ModelManager
# from ..utils.cost_tracker import CostTracker  # Module not found
from ..utils.token_counter import TokenCounter

logger = structlog.get_logger()


class FusionConfig(BaseModel):
    """融合配置"""
    
    enabled: bool = Field(default=True, description="是否启用融合")
    model: str = Field(default="gemini-2.5-flash", description="融合模型")
    temperature: float = Field(default=0.2, description="生成温度")
    prompt_template_path: str = Field(
        default="./prompts/MiniLLM_Memory_Prompt_Template_v3.md",
        description="提示模板路径"
    )
    token_limit: int = Field(default=800, description="输出token限制")
    language: str = Field(default="zh", description="输出语言")
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl_seconds: int = Field(default=3600, description="缓存过期时间")


class FusedMemory(BaseModel):
    """融合后的记忆"""
    
    content: str = Field(description="融合后的内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    source_units: List[str] = Field(default_factory=list, description="源记忆单元ID")
    token_count: int = Field(description="Token数量")
    fusion_model: str = Field(description="使用的融合模型")
    fusion_cost: float = Field(default=0.0, description="融合成本")


class MemoryFuser:
    """记忆融合器"""
    
    def __init__(
        self,
        config: FusionConfig,
        model_manager: ModelManager,
        cost_tracker: Optional[Any] = None
    ):
        self.config = config
        self.model_manager = model_manager
        self.cost_tracker = cost_tracker  # CostTracker module not available
        self.token_counter = TokenCounter()
        self._cache: Dict[str, FusedMemory] = {}
        self._prompt_template: Optional[str] = None
        self._load_prompt_template()
        
        logger.info(
            "memory_fuser_initialized",
            model=config.model,
            token_limit=config.token_limit,
            language=config.language
        )
    
    def _load_prompt_template(self) -> None:
        """加载提示模板"""
        try:
            template_path = Path(self.config.prompt_template_path)
            if template_path.exists():
                self._prompt_template = template_path.read_text(encoding="utf-8")
                logger.info("prompt_template_loaded", path=str(template_path))
            else:
                logger.warning(
                    "prompt_template_not_found",
                    path=str(template_path),
                    using_default=True
                )
                self._prompt_template = self._get_default_template()
        except Exception as e:
            logger.error("prompt_template_load_error", error=str(e))
            self._prompt_template = self._get_default_template()
    
    def _get_default_template(self) -> str:
        """获取默认模板"""
        return """You are a Memory Fusion Assistant. Your task is to fuse memory fragments into structured context.

**Input Fragments:**
{retrieved_passages}

**Your Task:**
1. Extract key technical information
2. Organize by relevance and timeline
3. Highlight unresolved issues
4. Keep technical identifiers precise

**Output Format:**
## 项目概况
- <概括当前任务/模块>

## 关键决策与修改
1. <日期> <描述> - <文件/函数>
...

## 待解决问题
- <问题描述>
...

## 重要函数/类
| 名称 | 描述 | 参数 | 返回值 |
|------|------|------|--------|
| func | desc | args | return |

## 错误摘要
```
<error logs if any>
```

**Constraints:**
- Maximum {token_limit} tokens
- Language: {language}
- Focus on actionable information"""
    
    async def fuse_memories(
        self,
        memory_units: List[MemoryUnitModel],
        query: str,
        max_tokens: Optional[int] = None
    ) -> FusedMemory:
        """
        融合记忆单元
        
        Args:
            memory_units: 要融合的记忆单元列表
            query: 当前查询
            max_tokens: 最大token数限制
            
        Returns:
            融合后的记忆
        """
        if not self.config.enabled:
            # 如果未启用融合，直接拼接
            return self._simple_concatenate(memory_units)
        
        # 检查缓存
        cache_key = self._generate_cache_key(memory_units, query)
        if self.config.cache_enabled and cache_key in self._cache:
            cached = self._cache[cache_key]
            if self._is_cache_valid(cached):
                logger.info("fusion_cache_hit", key=cache_key)
                return cached
        
        # 执行融合
        try:
            fused = await self._perform_fusion(
                memory_units,
                query,
                max_tokens or self.config.token_limit
            )
            
            # 缓存结果
            if self.config.cache_enabled:
                self._cache[cache_key] = fused
            
            return fused
            
        except Exception as e:
            logger.error("fusion_error", error=str(e))
            # 降级到简单拼接
            return self._simple_concatenate(memory_units)
    
    async def _perform_fusion(
        self,
        memory_units: List[MemoryUnitModel],
        query: str,
        max_tokens: int
    ) -> FusedMemory:
        """执行融合操作"""
        # 准备片段
        fragments = self._prepare_fragments(memory_units)
        
        # 构建提示
        prompt = self._build_fusion_prompt(fragments, query, max_tokens)
        
        # 调用模型
        start_time = asyncio.get_event_loop().time()
        
        try:
            response = await self.model_manager.generate_completion(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=max_tokens
            )
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 计算成本
            usage = response.usage if hasattr(response, 'usage') else {}
            cost = response.cost_usd if hasattr(response, 'cost_usd') else 0.0
            
            # 统计token
            token_count = self.token_counter.count_tokens(content)
            
            elapsed_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(
                "fusion_completed",
                model=self.config.model,
                input_units=len(memory_units),
                output_tokens=token_count,
                cost=cost,
                elapsed_time=elapsed_time
            )
            
            return FusedMemory(
                content=content,
                metadata={
                    "query": query,
                    "fusion_time": elapsed_time,
                    "input_count": len(memory_units)
                },
                source_units=[unit.id for unit in memory_units],
                token_count=token_count,
                fusion_model=self.config.model,
                fusion_cost=cost
            )
            
        except Exception as e:
            logger.error(
                "model_fusion_error",
                model=self.config.model,
                error=str(e)
            )
            raise
    
    def _prepare_fragments(self, memory_units: List[MemoryUnitModel]) -> str:
        """准备记忆片段"""
        fragments = []
        
        for i, unit in enumerate(memory_units):
            fragment = f"<fragment_{i:02d}>\n"
            fragment += f"Time: {unit.created_at}\n"
            fragment += f"Type: {unit.unit_type}\n"
            
            if unit.metadata:
                fragment += f"Metadata: {json.dumps(unit.metadata, ensure_ascii=False)}\n"
            
            fragment += f"Content:\n{unit.content}\n"
            fragment += f"</fragment_{i:02d}>"
            
            fragments.append(fragment)
        
        return "\n\n".join(fragments)
    
    def _build_fusion_prompt(
        self,
        fragments: str,
        query: str,
        max_tokens: int
    ) -> str:
        """构建融合提示"""
        if not self._prompt_template:
            self._load_prompt_template()
        
        prompt = self._prompt_template.format(
            retrieved_passages=fragments,
            query=query,
            token_limit=max_tokens,
            language=self.config.language
        )
        
        return prompt
    
    def _simple_concatenate(self, memory_units: List[MemoryUnitModel]) -> FusedMemory:
        """简单拼接记忆单元"""
        contents = []
        
        for unit in memory_units:
            content = f"[{unit.created_at}] {unit.unit_type}:\n{unit.content}\n"
            contents.append(content)
        
        combined = "\n---\n".join(contents)
        token_count = self.token_counter.count_tokens(combined)
        
        return FusedMemory(
            content=combined,
            metadata={"fusion_method": "simple_concatenation"},
            source_units=[unit.id for unit in memory_units],
            token_count=token_count,
            fusion_model="none",
            fusion_cost=0.0
        )
    
    def _generate_cache_key(
        self,
        memory_units: List[MemoryUnitModel],
        query: str
    ) -> str:
        """生成缓存键"""
        # 使用记忆单元ID和查询生成唯一键
        unit_ids = sorted([unit.id for unit in memory_units])
        key_str = f"{query}:{':'.join(unit_ids)}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
    
    def _is_cache_valid(self, cached: FusedMemory) -> bool:
        """检查缓存是否有效"""
        # 这里可以添加更复杂的缓存验证逻辑
        # 比如检查时间戳、版本等
        return True
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("fusion_cache_cleared")
    
    async def batch_fuse(
        self,
        memory_groups: List[Tuple[List[MemoryUnit], str]],
        max_tokens: Optional[int] = None
    ) -> List[FusedMemory]:
        """
        批量融合多组记忆
        
        Args:
            memory_groups: (记忆单元列表, 查询)元组列表
            max_tokens: 最大token数限制
            
        Returns:
            融合结果列表
        """
        tasks = [
            self.fuse_memories(units, query, max_tokens)
            for units, query in memory_groups
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        fused_memories = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "batch_fusion_error",
                    index=i,
                    error=str(result)
                )
                # 降级处理
                units, query = memory_groups[i]
                fused_memories.append(self._simple_concatenate(units))
            else:
                fused_memories.append(result)
        
        return fused_memories
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "cache_size": len(self._cache),
            "total_cost": self.cost_tracker.get_total_cost(),
            "model": self.config.model,
            "enabled": self.config.enabled
        }