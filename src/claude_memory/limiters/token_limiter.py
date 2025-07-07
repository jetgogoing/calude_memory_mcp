"""
Claude记忆管理MCP服务 - TokenLimiter模块

确保Claude接收的上下文不超过token限制。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

from ..models.data_models import MemoryUnit
from ..utils.token_counter import TokenCounter
from ..utils.model_manager import ModelManager

logger = structlog.get_logger()


class TruncationStrategy(str, Enum):
    """截断策略"""
    HEAD = "head"  # 保留开头
    TAIL = "tail"  # 保留结尾
    MIDDLE = "middle"  # 保留中间
    SMART = "smart"  # 智能截断


class PriorityLevel(str, Enum):
    """优先级级别"""
    CRITICAL = "critical"  # 关键信息
    HIGH = "high"  # 高优先级
    MEDIUM = "medium"  # 中等优先级
    LOW = "low"  # 低优先级


class LimiterConfig(BaseModel):
    """限制器配置"""
    
    default_limit: int = Field(default=20000, description="默认token限制")
    context_window: int = Field(default=200000, description="模型上下文窗口")
    reserve_tokens: int = Field(default=2000, description="保留token数")
    
    priority_limits: Dict[str, int] = Field(
        default_factory=lambda: {
            "global_mu": 8000,
            "quick_mu": 6000,
            "conversation": 4000,
            "error_log": 2000
        },
        description="各类型优先级限制"
    )
    
    truncation_strategy: TruncationStrategy = Field(
        default=TruncationStrategy.SMART,
        description="截断策略"
    )
    
    enable_compression: bool = Field(default=True, description="是否启用压缩")
    compression_model: str = Field(default="gemini-2.5-flash", description="压缩模型")
    compression_threshold: float = Field(default=0.8, description="压缩阈值")


class LimitedContent(BaseModel):
    """限制后的内容"""
    
    content: str = Field(description="限制后的内容")
    original_tokens: int = Field(description="原始token数")
    final_tokens: int = Field(description="最终token数")
    truncated: bool = Field(description="是否被截断")
    compressed: bool = Field(description="是否被压缩")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class TokenLimiter:
    """Token限制器"""
    
    def __init__(
        self,
        config: LimiterConfig,
        model_manager: Optional[ModelManager] = None
    ):
        self.config = config
        self.model_manager = model_manager
        self.token_counter = TokenCounter()
        
        logger.info(
            "token_limiter_initialized",
            default_limit=config.default_limit,
            strategy=config.truncation_strategy
        )
    
    def limit_content(
        self,
        content: str,
        max_tokens: Optional[int] = None,
        priority: PriorityLevel = PriorityLevel.MEDIUM
    ) -> LimitedContent:
        """
        限制内容长度
        
        Args:
            content: 要限制的内容
            max_tokens: 最大token数
            priority: 优先级
            
        Returns:
            限制后的内容
        """
        limit = max_tokens or self._get_limit_for_priority(priority)
        original_tokens = self.token_counter.count_tokens(content)
        
        # 如果未超限，直接返回
        if original_tokens <= limit:
            return LimitedContent(
                content=content,
                original_tokens=original_tokens,
                final_tokens=original_tokens,
                truncated=False,
                compressed=False,
                metadata={"priority": priority}
            )
        
        # 尝试压缩
        if self.config.enable_compression and self.model_manager:
            compressed = self._try_compress(content, limit, priority)
            if compressed:
                return compressed
        
        # 截断
        truncated = self._truncate_content(content, limit)
        final_tokens = self.token_counter.count_tokens(truncated)
        
        return LimitedContent(
            content=truncated,
            original_tokens=original_tokens,
            final_tokens=final_tokens,
            truncated=True,
            compressed=False,
            metadata={
                "priority": priority,
                "truncation_strategy": self.config.truncation_strategy
            }
        )
    
    def limit_units(
        self,
        units: List[MemoryUnit],
        total_limit: int,
        preserve_structure: bool = True
    ) -> Tuple[List[MemoryUnit], Dict[str, Any]]:
        """
        限制记忆单元列表的总token数
        
        Args:
            units: 记忆单元列表
            total_limit: 总token限制
            preserve_structure: 是否保留结构
            
        Returns:
            (限制后的单元列表, 统计信息)
        """
        # 计算每个单元的token数
        unit_tokens = []
        for unit in units:
            tokens = self.token_counter.count_tokens(unit.content)
            unit_tokens.append((unit, tokens))
        
        # 按优先级排序
        unit_tokens.sort(
            key=lambda x: (
                self._get_unit_priority(x[0]),
                x[0].relevance_score
            ),
            reverse=True
        )
        
        # 选择单元直到达到限制
        selected_units = []
        current_tokens = 0
        truncated_count = 0
        
        for unit, tokens in unit_tokens:
            if current_tokens + tokens <= total_limit:
                selected_units.append(unit)
                current_tokens += tokens
            elif preserve_structure:
                # 尝试截断单元内容
                remaining = total_limit - current_tokens
                if remaining > 100:  # 至少保留100个token
                    truncated_unit = self._truncate_unit(unit, remaining)
                    if truncated_unit:
                        selected_units.append(truncated_unit)
                        current_tokens += self.token_counter.count_tokens(
                            truncated_unit.content
                        )
                        truncated_count += 1
        
        stats = {
            "original_count": len(units),
            "selected_count": len(selected_units),
            "truncated_count": truncated_count,
            "original_tokens": sum(t for _, t in unit_tokens),
            "final_tokens": current_tokens
        }
        
        logger.info("units_limited", **stats)
        
        return selected_units, stats
    
    def _get_limit_for_priority(self, priority: PriorityLevel) -> int:
        """获取优先级对应的限制"""
        priority_multipliers = {
            PriorityLevel.CRITICAL: 1.0,
            PriorityLevel.HIGH: 0.8,
            PriorityLevel.MEDIUM: 0.6,
            PriorityLevel.LOW: 0.4
        }
        
        multiplier = priority_multipliers.get(priority, 0.6)
        return int(self.config.default_limit * multiplier)
    
    def _get_unit_priority(self, unit: MemoryUnit) -> int:
        """获取单元优先级分数"""
        type_priorities = {
            "global_mu": 4,
            "quick_mu": 3,
            "error_log": 3,
            "decision": 3,
            "conversation": 2,
            "code_snippet": 2,
            "documentation": 1
        }
        
        return type_priorities.get(unit.unit_type, 1)
    
    def _truncate_content(self, content: str, limit: int) -> str:
        """截断内容"""
        # 估算字符数（粗略估计1 token ≈ 4字符）
        char_limit = limit * 4
        
        if self.config.truncation_strategy == TruncationStrategy.HEAD:
            return content[:char_limit] + "..."
        
        elif self.config.truncation_strategy == TruncationStrategy.TAIL:
            return "..." + content[-char_limit:]
        
        elif self.config.truncation_strategy == TruncationStrategy.MIDDLE:
            half = char_limit // 2
            return content[:half] + "\n...[内容已截断]...\n" + content[-half:]
        
        else:  # SMART
            return self._smart_truncate(content, limit)
    
    def _smart_truncate(self, content: str, limit: int) -> str:
        """智能截断"""
        # 尝试保留完整的段落或句子
        lines = content.split('\n')
        result = []
        current_tokens = 0
        
        for line in lines:
            line_tokens = self.token_counter.count_tokens(line)
            if current_tokens + line_tokens > limit:
                # 如果是第一行就超限，截断这一行
                if not result:
                    remaining = limit - current_tokens
                    truncated_line = self._truncate_line(line, remaining)
                    result.append(truncated_line)
                break
            
            result.append(line)
            current_tokens += line_tokens
        
        return '\n'.join(result)
    
    def _truncate_line(self, line: str, token_limit: int) -> str:
        """截断单行"""
        # 按句子分割
        sentences = line.split('。')
        result = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.token_counter.count_tokens(sentence)
            if current_tokens + sentence_tokens > token_limit:
                break
            result.append(sentence)
            current_tokens += sentence_tokens
        
        if result:
            return '。'.join(result) + '。...'
        else:
            # 如果一个句子都放不下，按字符截断
            char_limit = token_limit * 4
            return line[:char_limit] + "..."
    
    def _truncate_unit(
        self,
        unit: MemoryUnit,
        token_limit: int
    ) -> Optional[MemoryUnit]:
        """截断记忆单元"""
        limited = self.limit_content(unit.content, token_limit)
        
        if limited.final_tokens > 0:
            # 创建新的单元副本
            return MemoryUnit(
                memory_id=unit.memory_id,
                conversation_id=unit.conversation_id,
                timestamp=unit.timestamp,
                content=limited.content,
                unit_type=unit.unit_type,
                relevance_score=unit.relevance_score,
                metadata={
                    **unit.metadata,
                    "truncated": True,
                    "original_tokens": limited.original_tokens
                }
            )
        
        return None
    
    async def _try_compress(
        self,
        content: str,
        limit: int,
        priority: PriorityLevel
    ) -> Optional[LimitedContent]:
        """尝试压缩内容"""
        if not self.model_manager:
            return None
        
        try:
            # 构建压缩提示
            prompt = f"""请将以下内容压缩到约{limit}个token以内，保留所有关键信息：

{content}

要求：
1. 保留所有技术细节、函数名、参数、错误信息
2. 去除冗余和重复内容
3. 使用简洁的表达方式
4. 优先级：{priority}"""
            
            response = await self.model_manager.generate_completion(
                model=self.config.compression_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=limit
            )
            
            compressed = response.get("content", "")
            compressed_tokens = self.token_counter.count_tokens(compressed)
            
            # 检查压缩效果
            if compressed_tokens <= limit and compressed_tokens < len(content):
                logger.info(
                    "content_compressed",
                    original_tokens=self.token_counter.count_tokens(content),
                    compressed_tokens=compressed_tokens,
                    compression_ratio=compressed_tokens / len(content)
                )
                
                return LimitedContent(
                    content=compressed,
                    original_tokens=self.token_counter.count_tokens(content),
                    final_tokens=compressed_tokens,
                    truncated=False,
                    compressed=True,
                    metadata={
                        "priority": priority,
                        "compression_model": self.config.compression_model
                    }
                )
            
        except Exception as e:
            logger.error("compression_error", error=str(e))
        
        return None
    
    def estimate_tokens(self, content: str) -> int:
        """估算token数"""
        return self.token_counter.count_tokens(content)
    
    def get_available_tokens(
        self,
        used_tokens: int,
        reserve: bool = True
    ) -> int:
        """获取可用token数"""
        total = self.config.context_window
        
        if reserve:
            total -= self.config.reserve_tokens
        
        return max(0, total - used_tokens)