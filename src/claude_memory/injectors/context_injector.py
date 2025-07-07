"""
Claude记忆管理MCP服务 - 上下文注入器

负责智能的上下文注入、记忆整合和Token预算管理。
支持多种注入策略和动态优化。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

from claude_memory.models.data_models import (
    ContextInjectionRequest,
    ContextInjectionResponse,
    MemoryUnitModel,
    MemoryUnitType,
    SearchQuery,
    SearchResult,
)
from claude_memory.config.settings import get_settings
from claude_memory.retrievers.semantic_retriever import SemanticRetriever, RetrievalRequest
from claude_memory.utils.text_processing import TextProcessor
from claude_memory.utils.error_handling import (
    handle_exceptions,
    with_retry,
    ProcessingError,
    RetryableError,
)

logger = structlog.get_logger(__name__)


class InjectionStrategy(BaseModel):
    """注入策略配置"""
    
    name: str
    priority: int = Field(ge=1, le=10)
    max_memories: int = Field(default=5, ge=1, le=20)
    token_budget: int = Field(default=2000, ge=100, le=10000)
    relevance_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    include_types: List[MemoryUnitType] = Field(default_factory=lambda: [MemoryUnitType.GLOBAL_MU, MemoryUnitType.QUICK_MU])
    template: str = "default"


class InjectionResult(BaseModel):
    """注入结果模型"""
    
    injected_context: str
    memories_used: List[MemoryUnitModel]
    tokens_used: int
    strategy_applied: str
    compression_ratio: float = Field(ge=0.0, le=1.0)
    relevance_scores: List[float]
    metadata: Optional[Dict[str, Any]] = None


class ContextInjector:
    """
    上下文注入器 - 负责智能的记忆注入
    
    功能特性:
    - 智能上下文注入
    - Token预算管理
    - 多种注入策略
    - 动态压缩优化
    - 相关性排序
    - 实时性能监控
    """
    
    def __init__(self, retriever: SemanticRetriever):
        self.settings = get_settings()
        self.retriever = retriever
        self.text_processor = TextProcessor()
        
        # 注入策略配置
        self.injection_strategies = {
            'conservative': InjectionStrategy(
                name='conservative',
                priority=1,
                max_memories=3,
                token_budget=1000,
                relevance_threshold=0.8,
                include_types=[MemoryUnitType.GLOBAL_MU],
                template='minimal'
            ),
            'balanced': InjectionStrategy(
                name='balanced',
                priority=5,
                max_memories=5,
                token_budget=2000,
                relevance_threshold=0.6,
                include_types=[MemoryUnitType.GLOBAL_MU, MemoryUnitType.QUICK_MU],
                template='standard'
            ),
            'comprehensive': InjectionStrategy(
                name='comprehensive',
                priority=10,
                max_memories=10,
                token_budget=4000,
                relevance_threshold=0.4,
                include_types=[MemoryUnitType.GLOBAL_MU, MemoryUnitType.QUICK_MU, MemoryUnitType.ARCHIVE],
                template='detailed'
            ),
        }
        
        # 上下文模板
        self.context_templates = {
            'minimal': self._minimal_template,
            'standard': self._standard_template,
            'detailed': self._detailed_template,
        }
        
        # 缓存
        self.injection_cache: Dict[str, InjectionResult] = {}
        self.max_cache_size = 200
        
        logger.info(
            "ContextInjector initialized",
            strategies=list(self.injection_strategies.keys()),
            templates=list(self.context_templates.keys()),
        )

    @handle_exceptions(logger=logger, reraise=True)
    @with_retry(max_attempts=2)
    async def inject_context(self, request: ContextInjectionRequest) -> ContextInjectionResponse:
        """
        注入相关上下文
        
        Args:
            request: 注入请求
            
        Returns:
            ContextInjectionResponse: 注入响应
        """
        start_time = datetime.utcnow()
        
        try:
            # 检查缓存
            cache_key = self._generate_cache_key(request)
            if cache_key in self.injection_cache:
                logger.debug("Using cached injection result", cache_key=cache_key)
                cached_result = self.injection_cache[cache_key]
                return ContextInjectionResponse(
                    enhanced_prompt=request.original_prompt + "\\n\\n" + cached_result.injected_context,
                    injected_memories=cached_result.memories_used,
                    tokens_used=cached_result.tokens_used,
                    processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    metadata=cached_result.metadata
                )
            
            # 选择注入策略
            strategy = self._select_injection_strategy(request)
            
            # 构建搜索查询
            search_query = SearchQuery(
                query=request.query_text or request.original_prompt,
                query_type='hybrid',
                context=request.context_hint or ""
            )
            
            # 检索相关记忆
            retrieval_request = RetrievalRequest(
                query=search_query,
                limit=strategy.max_memories * 2,  # 获取更多候选
                min_score=strategy.relevance_threshold,
                unit_types=strategy.include_types,
                rerank=True,
                hybrid_search=True
            )
            
            retrieval_result = await self.retriever.retrieve_memories(retrieval_request)
            
            if not retrieval_result.results:
                logger.info("No relevant memories found for injection")
                return ContextInjectionResponse(
                    enhanced_prompt=request.original_prompt,
                    injected_memories=[],
                    tokens_used=0,
                    processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    metadata={'strategy': strategy.name, 'memories_found': 0}
                )
            
            # 优化记忆选择
            selected_memories = await self._optimize_memory_selection(
                retrieval_result.results, strategy, request
            )
            
            # 生成注入上下文
            injection_result = await self._generate_injection_context(
                selected_memories, strategy, request
            )
            
            # 验证Token预算
            if injection_result.tokens_used > strategy.token_budget:
                logger.warning(
                    "Token budget exceeded, applying compression",
                    used=injection_result.tokens_used,
                    budget=strategy.token_budget
                )
                injection_result = await self._compress_injection_context(
                    injection_result, strategy.token_budget
                )
            
            # 构建最终响应
            enhanced_prompt = request.original_prompt
            if injection_result.injected_context:
                enhanced_prompt += "\\n\\n" + injection_result.injected_context
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            response = ContextInjectionResponse(
                enhanced_prompt=enhanced_prompt,
                injected_memories=injection_result.memories_used,
                tokens_used=injection_result.tokens_used,
                processing_time_ms=processing_time,
                metadata={
                    'strategy': injection_result.strategy_applied,
                    'memories_found': len(retrieval_result.results),
                    'memories_used': len(injection_result.memories_used),
                    'compression_ratio': injection_result.compression_ratio,
                    'average_relevance': sum(injection_result.relevance_scores) / len(injection_result.relevance_scores) if injection_result.relevance_scores else 0,
                    'retrieval_time_ms': retrieval_result.search_time_ms,
                    'injection_strategy': strategy.name,
                }
            )
            
            # 缓存结果
            await self._cache_injection_result(cache_key, injection_result)
            
            logger.info(
                "Context injection completed",
                strategy=strategy.name,
                memories_used=len(injection_result.memories_used),
                tokens_used=injection_result.tokens_used,
                processing_time_ms=processing_time,
                compression_ratio=injection_result.compression_ratio,
            )
            
            return response
            
        except Exception as e:
            logger.error(
                "Context injection failed",
                error=str(e),
                query_text=request.query_text[:50] if request.query_text else "N/A"
            )
            raise ProcessingError(f"Context injection failed: {str(e)}")

    async def _optimize_memory_selection(
        self,
        candidates: List[SearchResult],
        strategy: InjectionStrategy,
        request: ContextInjectionRequest
    ) -> List[SearchResult]:
        """
        优化记忆选择
        
        Args:
            candidates: 候选记忆列表
            strategy: 注入策略
            request: 注入请求
            
        Returns:
            List[SearchResult]: 优化后的记忆列表
        """
        if not candidates:
            return []
        
        # 按相关性排序
        sorted_candidates = sorted(
            candidates, 
            key=lambda x: x.relevance_score, 
            reverse=True
        )
        
        # 应用多样性过滤
        selected_memories = []
        used_keywords = set()
        token_count = 0
        
        for candidate in sorted_candidates:
            # 检查数量限制
            if len(selected_memories) >= strategy.max_memories:
                break
            
            # 检查Token预算
            memory_tokens = candidate.memory_unit.token_count
            if token_count + memory_tokens > strategy.token_budget:
                # 尝试压缩或跳过
                if len(selected_memories) == 0:  # 至少保留一个记忆
                    selected_memories.append(candidate)
                    token_count += memory_tokens
                break
            
            # 多样性检查：避免过度重复的关键词
            memory_keywords = set(candidate.memory_unit.keywords)
            keyword_overlap = len(memory_keywords & used_keywords) / len(memory_keywords) if memory_keywords else 0
            
            if keyword_overlap < 0.7:  # 允许30%以下的重叠
                selected_memories.append(candidate)
                used_keywords.update(memory_keywords)
                token_count += memory_tokens
        
        # 按记忆类型重新排序：Global > Quick > Archive
        type_priority = {
            MemoryUnitType.GLOBAL_MU: 3,
            MemoryUnitType.QUICK_MU: 2,
            MemoryUnitType.ARCHIVE: 1,
        }
        
        selected_memories.sort(
            key=lambda x: (
                type_priority.get(x.memory_unit.unit_type, 0),
                x.relevance_score
            ),
            reverse=True
        )
        
        logger.debug(
            "Memory selection optimized",
            candidates_count=len(candidates),
            selected_count=len(selected_memories),
            estimated_tokens=token_count,
            strategy=strategy.name
        )
        
        return selected_memories

    async def _generate_injection_context(
        self,
        memories: List[SearchResult],
        strategy: InjectionStrategy,
        request: ContextInjectionRequest
    ) -> InjectionResult:
        """
        生成注入上下文
        
        Args:
            memories: 选中的记忆列表
            strategy: 注入策略
            request: 注入请求
            
        Returns:
            InjectionResult: 注入结果
        """
        if not memories:
            return InjectionResult(
                injected_context="",
                memories_used=[],
                tokens_used=0,
                strategy_applied=strategy.name,
                compression_ratio=0.0,
                relevance_scores=[],
                metadata={}
            )
        
        # 选择上下文模板
        template_func = self.context_templates.get(
            strategy.template, 
            self._standard_template
        )
        
        # 生成上下文
        injected_context = await template_func(memories, request)
        
        # 计算Token数量
        tokens_used = await self.text_processor.count_tokens(injected_context)
        
        # 计算压缩比
        original_tokens = sum(memory.memory_unit.token_count for memory in memories)
        compression_ratio = tokens_used / original_tokens if original_tokens > 0 else 0.0
        
        return InjectionResult(
            injected_context=injected_context,
            memories_used=[memory.memory_unit for memory in memories],
            tokens_used=tokens_used,
            strategy_applied=strategy.name,
            compression_ratio=compression_ratio,
            relevance_scores=[memory.relevance_score for memory in memories],
            metadata={
                'template_used': strategy.template,
                'original_tokens': original_tokens,
                'memory_count': len(memories),
            }
        )

    async def _minimal_template(
        self, memories: List[SearchResult], request: ContextInjectionRequest
    ) -> str:
        """
        最小化模板
        
        Args:
            memories: 记忆列表
            request: 注入请求
            
        Returns:
            str: 格式化的上下文
        """
        if not memories:
            return ""
        
        context_parts = ["相关记忆:"]
        
        for i, memory in enumerate(memories[:3], 1):  # 最多3个记忆
            memory_unit = memory.memory_unit
            context_parts.append(f"{i}. {memory_unit.title}: {memory_unit.summary[:200]}...")
        
        return "\\n".join(context_parts)

    async def _standard_template(
        self, memories: List[SearchResult], request: ContextInjectionRequest
    ) -> str:
        """
        标准模板
        
        Args:
            memories: 记忆列表
            request: 注入请求
            
        Returns:
            str: 格式化的上下文
        """
        if not memories:
            return ""
        
        context_parts = [
            "=== 相关历史记忆 ===",
            f"基于查询找到 {len(memories)} 条相关记忆:\\n"
        ]
        
        for i, memory in enumerate(memories, 1):
            memory_unit = memory.memory_unit
            relevance = memory.relevance_score
            
            context_parts.append(f"记忆 {i} [相关性: {relevance:.2f}]")
            context_parts.append(f"标题: {memory_unit.title}")
            context_parts.append(f"摘要: {memory_unit.summary}")
            
            if memory_unit.keywords:
                context_parts.append(f"关键词: {', '.join(memory_unit.keywords[:5])}")
            
            context_parts.append(f"时间: {memory_unit.created_at.strftime('%Y-%m-%d %H:%M')}")
            context_parts.append("")  # 空行分隔
        
        context_parts.append("=== 记忆结束 ===")
        
        return "\\n".join(context_parts)

    async def _detailed_template(
        self, memories: List[SearchResult], request: ContextInjectionRequest
    ) -> str:
        """
        详细模板
        
        Args:
            memories: 记忆列表
            request: 注入请求
            
        Returns:
            str: 格式化的上下文
        """
        if not memories:
            return ""
        
        context_parts = [
            "=== 详细历史记忆上下文 ===",
            f"查询: {request.query_text or '隐式查询'}",
            f"找到 {len(memories)} 条高度相关的历史记忆:\\n"
        ]
        
        # 按类型分组
        grouped_memories = {}
        for memory in memories:
            unit_type = memory.memory_unit.unit_type
            if unit_type not in grouped_memories:
                grouped_memories[unit_type] = []
            grouped_memories[unit_type].append(memory)
        
        # 按优先级顺序处理
        type_names = {
            MemoryUnitType.GLOBAL_MU: "全局重要记忆",
            MemoryUnitType.QUICK_MU: "近期会话记忆", 
            MemoryUnitType.ARCHIVE: "历史归档记忆"
        }
        
        for unit_type in [MemoryUnitType.GLOBAL_MU, MemoryUnitType.QUICK_MU, MemoryUnitType.ARCHIVE]:
            if unit_type not in grouped_memories:
                continue
            
            context_parts.append(f"## {type_names[unit_type]}")
            
            for i, memory in enumerate(grouped_memories[unit_type], 1):
                memory_unit = memory.memory_unit
                relevance = memory.relevance_score
                
                context_parts.append(f"### 记忆 {i} [相关性: {relevance:.2f}]")
                context_parts.append(f"**标题**: {memory_unit.title}")
                context_parts.append(f"**摘要**: {memory_unit.summary}")
                
                if memory_unit.content and memory_unit.content != memory_unit.summary:
                    context_parts.append(f"**详细内容**: {memory_unit.content[:500]}...")
                
                if memory_unit.keywords:
                    context_parts.append(f"**关键词**: {', '.join(memory_unit.keywords)}")
                
                context_parts.append(f"**时间**: {memory_unit.created_at.strftime('%Y-%m-%d %H:%M')}")
                
                # 匹配信息
                if memory.matched_keywords:
                    context_parts.append(f"**匹配关键词**: {', '.join(memory.matched_keywords)}")
                
                context_parts.append("")  # 空行分隔
            
            context_parts.append("")  # 类型间分隔
        
        context_parts.append("=== 上下文结束 ===")
        
        return "\\n".join(context_parts)

    async def _compress_injection_context(
        self, injection_result: InjectionResult, target_budget: int
    ) -> InjectionResult:
        """
        压缩注入上下文
        
        Args:
            injection_result: 原始注入结果
            target_budget: 目标Token预算
            
        Returns:
            InjectionResult: 压缩后的注入结果
        """
        if injection_result.tokens_used <= target_budget:
            return injection_result
        
        logger.info(
            "Compressing injection context",
            original_tokens=injection_result.tokens_used,
            target_budget=target_budget
        )
        
        # 策略1: 减少记忆数量
        if len(injection_result.memories_used) > 1:
            # 保留最相关的记忆
            keep_count = max(1, len(injection_result.memories_used) // 2)
            
            # 重新生成上下文（使用更简洁的模板）
            top_memories = []
            for i, memory_unit in enumerate(injection_result.memories_used[:keep_count]):
                # 创建SearchResult对象用于模板生成
                search_result = SearchResult(
                    memory_unit=memory_unit,
                    relevance_score=injection_result.relevance_scores[i] if i < len(injection_result.relevance_scores) else 0.8,
                    match_type='compressed',
                    matched_keywords=[],
                    metadata={}
                )
                top_memories.append(search_result)
            
            # 使用最小模板重新生成
            compressed_context = await self._minimal_template(
                top_memories, 
                ContextInjectionRequest(original_prompt="", query_text="")
            )
            
            compressed_tokens = await self.text_processor.count_tokens(compressed_context)
            
            if compressed_tokens <= target_budget:
                return InjectionResult(
                    injected_context=compressed_context,
                    memories_used=injection_result.memories_used[:keep_count],
                    tokens_used=compressed_tokens,
                    strategy_applied=injection_result.strategy_applied + "_compressed",
                    compression_ratio=compressed_tokens / injection_result.tokens_used,
                    relevance_scores=injection_result.relevance_scores[:keep_count],
                    metadata={
                        **injection_result.metadata,
                        'compression_applied': True,
                        'compression_method': 'memory_reduction'
                    }
                )
        
        # 策略2: 截断内容
        words = injection_result.injected_context.split()
        target_word_count = int(len(words) * (target_budget / injection_result.tokens_used))
        truncated_context = " ".join(words[:target_word_count]) + "..."
        
        truncated_tokens = await self.text_processor.count_tokens(truncated_context)
        
        return InjectionResult(
            injected_context=truncated_context,
            memories_used=injection_result.memories_used,
            tokens_used=truncated_tokens,
            strategy_applied=injection_result.strategy_applied + "_truncated",
            compression_ratio=truncated_tokens / injection_result.tokens_used,
            relevance_scores=injection_result.relevance_scores,
            metadata={
                **injection_result.metadata,
                'compression_applied': True,
                'compression_method': 'content_truncation',
                'original_word_count': len(words),
                'truncated_word_count': target_word_count
            }
        )

    def _select_injection_strategy(self, request: ContextInjectionRequest) -> InjectionStrategy:
        """
        选择注入策略
        
        Args:
            request: 注入请求
            
        Returns:
            InjectionStrategy: 选择的策略
        """
        # 如果请求中指定了策略
        if request.injection_mode and request.injection_mode in self.injection_strategies:
            return self.injection_strategies[request.injection_mode]
        
        # 根据查询复杂度自动选择
        if request.query_text:
            query_length = len(request.query_text)
            if query_length < 50:
                return self.injection_strategies['conservative']
            elif query_length < 200:
                return self.injection_strategies['balanced']
            else:
                return self.injection_strategies['comprehensive']
        
        # 默认使用平衡策略
        return self.injection_strategies['balanced']

    def _generate_cache_key(self, request: ContextInjectionRequest) -> str:
        """
        生成缓存键
        
        Args:
            request: 注入请求
            
        Returns:
            str: 缓存键
        """
        import hashlib
        
        key_data = (
            request.original_prompt +
            (request.query_text or "") +
            (request.context_hint or "") +
            (request.injection_mode or "auto")
        )
        
        return f"injection_{hashlib.md5(key_data.encode()).hexdigest()}"

    async def _cache_injection_result(self, cache_key: str, result: InjectionResult) -> None:
        """
        缓存注入结果
        
        Args:
            cache_key: 缓存键
            result: 注入结果
        """
        # 控制缓存大小
        if len(self.injection_cache) >= self.max_cache_size:
            # 删除最旧的一半缓存
            old_keys = list(self.injection_cache.keys())[:self.max_cache_size // 2]
            for key in old_keys:
                del self.injection_cache[key]
        
        self.injection_cache[cache_key] = result

    @handle_exceptions(logger=logger, default_return=[])
    async def get_injection_strategies(self) -> List[Dict[str, Any]]:
        """
        获取可用的注入策略
        
        Returns:
            List[Dict[str, Any]]: 策略列表
        """
        strategies = []
        for name, strategy in self.injection_strategies.items():
            strategies.append({
                'name': name,
                'priority': strategy.priority,
                'max_memories': strategy.max_memories,
                'token_budget': strategy.token_budget,
                'relevance_threshold': strategy.relevance_threshold,
                'include_types': [t.value for t in strategy.include_types],
                'template': strategy.template,
                'description': f"优先级{strategy.priority}，最多{strategy.max_memories}条记忆，{strategy.token_budget}Token预算"
            })
        
        return strategies

    @handle_exceptions(logger=logger, reraise=True)
    async def update_injection_strategy(
        self, 
        strategy_name: str, 
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新注入策略
        
        Args:
            strategy_name: 策略名称
            updates: 更新的参数
            
        Returns:
            bool: 是否更新成功
        """
        if strategy_name not in self.injection_strategies:
            raise ProcessingError(f"Strategy '{strategy_name}' not found")
        
        strategy = self.injection_strategies[strategy_name]
        
        # 更新策略参数
        for key, value in updates.items():
            if hasattr(strategy, key):
                setattr(strategy, key, value)
            else:
                logger.warning(f"Unknown strategy parameter: {key}")
        
        logger.info(
            "Injection strategy updated",
            strategy_name=strategy_name,
            updates=updates
        )
        
        return True