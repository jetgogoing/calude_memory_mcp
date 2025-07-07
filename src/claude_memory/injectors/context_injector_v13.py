"""
Claude记忆管理MCP服务 - 上下文注入器 v1.3

集成MemoryFuser、PromptBuilder和TokenLimiter的新工作流。
支持embedding-only模式和智能压缩策略。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

from ..models.data_models import (
    MemoryUnit,
    MemoryUnitType,
)
from ..config.settings import get_settings
from ..retrievers.semantic_retriever import SemanticRetriever
from ..fusers.memory_fuser import MemoryFuser, FusionConfig
from ..builders.prompt_builder import PromptBuilder, BuilderConfig
from ..limiters.token_limiter import TokenLimiter, LimiterConfig, PriorityLevel
from ..utils.model_manager import ModelManager
from ..utils.cost_tracker import CostTracker
from ..utils.token_counter import TokenCounter

logger = structlog.get_logger(__name__)


class InjectionRequest(BaseModel):
    """注入请求"""
    
    query: str = Field(description="用户查询")
    conversation_id: str = Field(description="会话ID")
    max_tokens: Optional[int] = Field(default=None, description="最大token限制")
    strategy: str = Field(default="balanced", description="注入策略")
    include_fused: bool = Field(default=True, description="是否包含融合内容")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InjectionResponse(BaseModel):
    """注入响应"""
    
    content: str = Field(description="注入的上下文内容")
    token_count: int = Field(description="Token数量")
    memory_count: int = Field(description="包含的记忆数量")
    fused: bool = Field(description="是否使用了融合")
    cost: float = Field(description="处理成本")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InjectionStrategy(str):
    """注入策略"""
    MINIMAL = "minimal"  # 最小化，只包含最相关的
    BALANCED = "balanced"  # 平衡，适中的上下文
    COMPREHENSIVE = "comprehensive"  # 全面，包含尽可能多的上下文
    EMBEDDING_ONLY = "embedding_only"  # 仅嵌入模式


class ContextInjectorV13:
    """
    上下文注入器 v1.3
    
    实现新的工作流：检索 → 融合 → 构建 → 限制 → 注入
    """
    
    def __init__(
        self,
        retriever: SemanticRetriever,
        model_manager: ModelManager,
        cost_tracker: Optional[CostTracker] = None
    ):
        self.settings = get_settings()
        self.retriever = retriever
        self.model_manager = model_manager
        self.cost_tracker = cost_tracker or CostTracker()
        self.token_counter = TokenCounter()
        
        # 初始化子组件
        self._init_components()
        
        logger.info(
            "context_injector_v13_initialized",
            memory_mode=self.settings.memory.default_memory_mode,
            fuser_enabled=self.settings.memory.fuser_enabled
        )
    
    def _init_components(self) -> None:
        """初始化子组件"""
        # 融合器配置
        fusion_config = FusionConfig(
            enabled=self.settings.memory.fuser_enabled,
            model=self.settings.memory.fuser_model,
            temperature=self.settings.memory.fuser_temperature,
            token_limit=self.settings.memory.fuser_token_limit,
            language=self.settings.memory.fuser_language,
            prompt_template_path="./prompts/memory_fusion_prompt_programming.txt"
        )
        self.fuser = MemoryFuser(
            config=fusion_config,
            model_manager=self.model_manager,
            cost_tracker=self.cost_tracker
        )
        
        # 构建器配置
        builder_config = BuilderConfig(
            enable_deduplication=True,
            group_by_type=True,
            context_prefix="以下是相关的历史上下文信息：\n\n",
            context_suffix="\n\n基于以上历史信息，请回答用户的问题。"
        )
        self.builder = PromptBuilder(config=builder_config)
        
        # 限制器配置
        limiter_config = LimiterConfig(
            default_limit=self.settings.memory.token_budget_limit,
            context_window=200000,  # Claude的上下文窗口
            reserve_tokens=2000,
            truncation_strategy="smart",
            enable_compression=True,
            compression_model=self.settings.memory.fuser_model
        )
        self.limiter = TokenLimiter(
            config=limiter_config,
            model_manager=self.model_manager
        )
    
    async def inject_context(
        self,
        request: InjectionRequest
    ) -> InjectionResponse:
        """
        注入上下文
        
        实现v1.3工作流：
        1. 向量检索相关记忆
        2. 使用MemoryFuser融合记忆片段
        3. 使用PromptBuilder构建提示
        4. 使用TokenLimiter限制长度
        5. 返回最终上下文
        """
        start_time = asyncio.get_event_loop().time()
        total_cost = 0.0
        
        try:
            # 1. 检索相关记忆
            memory_units = await self._retrieve_memories(
                request.query,
                request.conversation_id,
                request.strategy
            )
            
            if not memory_units:
                logger.warning("no_memories_found", query=request.query)
                return InjectionResponse(
                    content="",
                    token_count=0,
                    memory_count=0,
                    fused=False,
                    cost=0.0,
                    metadata={"reason": "no_memories_found"}
                )
            
            # 2. 判断是否需要融合
            should_fuse = self._should_fuse(request, memory_units)
            fused_content = None
            
            if should_fuse and request.include_fused:
                # 执行融合
                fused_memory = await self.fuser.fuse_memories(
                    memory_units,
                    request.query,
                    self.settings.memory.fuser_token_limit
                )
                fused_content = fused_memory.content
                total_cost += fused_memory.fusion_cost
            
            # 3. 构建提示
            built_prompt = self.builder.build(
                memory_units,
                request.query,
                request.max_tokens,
                fused_content
            )
            
            # 4. 限制token
            priority = self._get_priority_level(request.strategy)
            limited_content = self.limiter.limit_content(
                built_prompt.content,
                request.max_tokens or self.settings.memory.token_budget_limit,
                priority
            )
            
            # 5. 计算总成本
            elapsed_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(
                "context_injection_completed",
                query=request.query,
                memory_count=len(memory_units),
                fused=bool(fused_content),
                token_count=limited_content.final_tokens,
                cost=total_cost,
                elapsed_time=elapsed_time
            )
            
            return InjectionResponse(
                content=limited_content.content,
                token_count=limited_content.final_tokens,
                memory_count=len(memory_units),
                fused=bool(fused_content),
                cost=total_cost,
                metadata={
                    "strategy": request.strategy,
                    "truncated": limited_content.truncated,
                    "compressed": limited_content.compressed,
                    "elapsed_time": elapsed_time
                }
            )
            
        except Exception as e:
            logger.error(
                "context_injection_error",
                error=str(e),
                query=request.query
            )
            raise
    
    async def _retrieve_memories(
        self,
        query: str,
        conversation_id: str,
        strategy: str
    ) -> List[MemoryUnit]:
        """检索相关记忆 (v1.4: 固定Top-20→Top-5策略)"""
        # v1.4: 固定使用Top-20初检，后续通过rerank返回Top-5
        top_k = self.settings.memory.retrieval_top_k  # 固定为20
        
        # 执行检索（内部会自动进行rerank并返回Top-5）
        search_results = await self.retriever.search(
            query=query,
            top_k=top_k,
            filters={
                "conversation_id": conversation_id
            } if conversation_id else None
        )
        
        # 转换为MemoryUnit列表
        memory_units = []
        for result in search_results:
            if hasattr(result, "memory_unit"):
                memory_units.append(result.memory_unit)
        
        logger.info(
            "memories_retrieved",
            query=query[:50],
            initial_candidates=top_k,
            final_results=len(memory_units),
            strategy="fixed_top20_to_top5"
        )
        
        return memory_units
    
    def _should_fuse(
        self,
        request: InjectionRequest,
        memory_units: List[MemoryUnit]
    ) -> bool:
        """判断是否需要融合 (v1.4: 直接读取环境变量配置)"""
        # v1.4: 简化逻辑，直接通过环境变量控制
        return self.settings.memory.fuser_enabled
    
    # v1.4: 移除不再需要的策略相关方法
    # _get_retrieval_top_k 和 _get_priority_level 已被移除
    # 现在使用固定的Top-20→Top-5策略和Medium优先级
    
    def _get_priority_level(self, strategy: str) -> PriorityLevel:
        """获取优先级 (v1.4: 简化为固定Medium优先级)"""
        # v1.4: 简化策略，固定使用Medium优先级
        return PriorityLevel.MEDIUM
    
    async def handle_manual_review(
        self,
        conversation_id: str
    ) -> str:
        """
        处理手动回顾命令
        
        当用户输入 /memory review 时调用
        """
        try:
            # 获取最近的记忆
            recent_memories = await self._retrieve_memories(
                query="",  # 空查询获取最新的
                conversation_id=conversation_id,
                strategy=InjectionStrategy.COMPREHENSIVE
            )
            
            if not recent_memories:
                return "暂无可回顾的记忆。"
            
            # 使用重型模型生成总结
            summary_prompt = f"""请为以下对话历史生成一个全面的总结，包括：
1. 主要讨论的主题和决策
2. 解决的问题和遇到的挑战
3. 重要的代码修改和架构变更
4. 待解决的问题和后续计划

对话历史：
{self._format_memories_for_summary(recent_memories)}
"""
            
            response = await self.model_manager.generate_completion(
                model=self.settings.memory.summary_model,
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.3,
                max_tokens=self.settings.memory.summary_max_tokens
            )
            
            summary = response.get("content", "")
            
            # 记录成本
            usage = response.get("usage", {})
            cost = self.cost_tracker.calculate_cost(
                self.settings.memory.summary_model,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0)
            )
            
            logger.info(
                "manual_review_completed",
                conversation_id=conversation_id,
                memory_count=len(recent_memories),
                cost=cost
            )
            
            return f"## 对话历史回顾\n\n{summary}"
            
        except Exception as e:
            logger.error(
                "manual_review_error",
                error=str(e),
                conversation_id=conversation_id
            )
            return f"回顾生成失败：{str(e)}"
    
    def _format_memories_for_summary(
        self,
        memories: List[MemoryUnit]
    ) -> str:
        """格式化记忆用于总结"""
        formatted = []
        
        for memory in memories:
            timestamp = memory.timestamp.strftime("%Y-%m-%d %H:%M")
            formatted.append(
                f"[{timestamp}] {memory.unit_type}:\n{memory.content}\n"
            )
        
        return "\n---\n".join(formatted)
    
    async def get_injection_stats(
        self,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取注入统计信息"""
        stats = {
            "mode": self.settings.memory.default_memory_mode,
            "fuser_enabled": self.settings.memory.fuser_enabled,
            "fuser_stats": self.fuser.get_stats(),
            "total_cost": self.cost_tracker.get_total_cost(),
            "daily_cost_estimate": self.cost_tracker.get_daily_estimate()
        }
        
        # 检查是否接近预算限制
        if stats["daily_cost_estimate"] > self.settings.cost.daily_budget_usd * 0.8:
            stats["budget_warning"] = True
            stats["budget_usage_percent"] = (
                stats["daily_cost_estimate"] / 
                self.settings.cost.daily_budget_usd * 100
            )
        
        return stats