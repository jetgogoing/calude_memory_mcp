"""
Claude记忆管理MCP服务 - 语义压缩器 v1.3

支持按需调用模式，仅在特定条件下生成记忆单元。
默认使用原文嵌入，降低成本。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog
from pydantic import BaseModel, Field

from ..models.data_models import (
    ConversationModel,
    MessageModel,
    MemoryUnit,
    MemoryUnitType
)
from ..config.settings import get_settings
from ..utils.model_manager import ModelManager
from ..utils.embedding_manager import EmbeddingManager
from ..utils.cost_tracker import CostTracker
from ..utils.token_counter import TokenCounter

logger = structlog.get_logger(__name__)


class CompressionTrigger(BaseModel):
    """压缩触发条件"""
    
    manual_command: bool = Field(default=False, description="手动命令触发")
    keyword_match: bool = Field(default=False, description="关键词匹配触发")
    matched_keywords: List[str] = Field(default_factory=list, description="匹配的关键词")
    token_threshold: bool = Field(default=False, description="Token阈值触发")
    time_threshold: bool = Field(default=False, description="时间阈值触发")


class CompressionRequest(BaseModel):
    """压缩请求"""
    
    conversation_id: str = Field(description="会话ID")
    messages: List[MessageModel] = Field(description="消息列表")
    force_compression: bool = Field(default=False, description="强制压缩")
    compression_type: str = Field(default="auto", description="压缩类型")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CompressionResult(BaseModel):
    """压缩结果"""
    
    memory_units: List[MemoryUnit] = Field(description="生成的记忆单元")
    embeddings_generated: int = Field(description="生成的嵌入数量")
    compression_performed: bool = Field(description="是否执行了压缩")
    trigger: CompressionTrigger = Field(description="触发条件")
    cost: float = Field(description="处理成本")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticCompressorV13:
    """
    语义压缩器 v1.3
    
    支持：
    - embedding-only模式：默认只生成嵌入，不压缩
    - 条件触发：基于关键词、命令或阈值触发压缩
    - 成本优化：最小化API调用
    """
    
    def __init__(
        self,
        model_manager: ModelManager,
        embedding_manager: EmbeddingManager,
        cost_tracker: Optional[CostTracker] = None
    ):
        self.settings = get_settings()
        self.model_manager = model_manager
        self.embedding_manager = embedding_manager
        self.cost_tracker = cost_tracker or CostTracker()
        self.token_counter = TokenCounter()
        
        # 缓存已处理的消息ID
        self._processed_message_ids: Set[str] = set()
        
        logger.info(
            "semantic_compressor_v13_initialized",
            memory_mode=self.settings.memory.default_memory_mode,
            auto_keywords=self.settings.memory.summary_auto_trigger_keywords
        )
    
    async def process_conversation(
        self,
        request: CompressionRequest
    ) -> CompressionResult:
        """
        处理会话
        
        v1.3工作流：
        1. 检查触发条件
        2. 如果不触发压缩，仅生成嵌入
        3. 如果触发压缩，执行智能压缩
        """
        start_time = asyncio.get_event_loop().time()
        total_cost = 0.0
        
        # 检查触发条件
        trigger = self._check_triggers(request)
        
        # 过滤未处理的消息
        new_messages = self._filter_new_messages(request.messages)
        
        if not new_messages:
            logger.info(
                "no_new_messages",
                conversation_id=request.conversation_id
            )
            return CompressionResult(
                memory_units=[],
                embeddings_generated=0,
                compression_performed=False,
                trigger=trigger,
                cost=0.0,
                metadata={"reason": "no_new_messages"}
            )
        
        # 决定是否压缩
        should_compress = self._should_compress(trigger, request)
        
        if should_compress:
            # 执行压缩
            result = await self._perform_compression(
                request.conversation_id,
                new_messages,
                trigger
            )
        else:
            # 仅生成嵌入
            result = await self._perform_embedding_only(
                request.conversation_id,
                new_messages
            )
        
        # 记录已处理的消息
        self._mark_messages_processed(new_messages)
        
        # 计算总成本
        result.cost = self.cost_tracker.get_session_cost()
        
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        logger.info(
            "conversation_processed",
            conversation_id=request.conversation_id,
            message_count=len(new_messages),
            compression_performed=result.compression_performed,
            embeddings_generated=result.embeddings_generated,
            cost=result.cost,
            elapsed_time=elapsed_time
        )
        
        return result
    
    def _check_triggers(self, request: CompressionRequest) -> CompressionTrigger:
        """检查触发条件"""
        trigger = CompressionTrigger()
        
        # 1. 检查手动命令
        for msg in request.messages:
            if self.settings.memory.summary_manual_trigger_command in msg.content:
                trigger.manual_command = True
                break
        
        # 2. 检查关键词
        all_content = " ".join(msg.content for msg in request.messages)
        for keyword in self.settings.memory.summary_auto_trigger_keywords:
            if keyword.lower() in all_content.lower():
                trigger.keyword_match = True
                trigger.matched_keywords.append(keyword)
        
        # 3. 检查token阈值
        total_tokens = sum(
            self.token_counter.count_tokens(msg.content)
            for msg in request.messages
        )
        if total_tokens > 5000:  # 阈值可配置
            trigger.token_threshold = True
        
        # 4. 检查时间阈值（例如：每24小时）
        # 这里简化处理，实际应该基于上次压缩时间
        if len(request.messages) > 50:  # 消息数量阈值
            trigger.time_threshold = True
        
        return trigger
    
    def _should_compress(
        self,
        trigger: CompressionTrigger,
        request: CompressionRequest
    ) -> bool:
        """判断是否应该压缩"""
        # 强制压缩
        if request.force_compression:
            return True
        
        # intelligent-compression模式总是压缩
        if self.settings.memory.default_memory_mode == "intelligent-compression":
            return True
        
        # embedding-only模式下检查触发条件
        if self.settings.memory.default_memory_mode == "embedding-only":
            return (
                trigger.manual_command or
                trigger.keyword_match or
                trigger.token_threshold or
                trigger.time_threshold
            )
        
        # hybrid模式下的混合策略
        if self.settings.memory.default_memory_mode == "hybrid":
            return trigger.keyword_match or trigger.manual_command
        
        return False
    
    async def _perform_compression(
        self,
        conversation_id: str,
        messages: List[MessageModel],
        trigger: CompressionTrigger
    ) -> CompressionResult:
        """执行压缩"""
        memory_units = []
        embeddings_generated = 0
        
        # 根据触发类型选择压缩策略
        if trigger.manual_command:
            # 生成全面的总结
            units = await self._generate_comprehensive_summary(
                conversation_id,
                messages
            )
            memory_units.extend(units)
        
        elif trigger.keyword_match:
            # 生成重点总结
            units = await self._generate_focused_summary(
                conversation_id,
                messages,
                trigger.matched_keywords
            )
            memory_units.extend(units)
        
        else:
            # 生成标准压缩
            units = await self._generate_standard_compression(
                conversation_id,
                messages
            )
            memory_units.extend(units)
        
        # 为所有单元生成嵌入
        for unit in memory_units:
            embedding = await self.embedding_manager.generate_embedding(
                unit.content,
                model=self.settings.models.default_embedding_model
            )
            unit.embedding = embedding
            embeddings_generated += 1
        
        return CompressionResult(
            memory_units=memory_units,
            embeddings_generated=embeddings_generated,
            compression_performed=True,
            trigger=trigger,
            cost=0.0,  # 将在外部计算
            metadata={
                "compression_type": "intelligent",
                "model_used": self.settings.memory.summary_model
            }
        )
    
    async def _perform_embedding_only(
        self,
        conversation_id: str,
        messages: List[MessageModel]
    ) -> CompressionResult:
        """仅执行嵌入"""
        memory_units = []
        embeddings_generated = 0
        
        # 将每条消息转换为记忆单元
        for msg in messages:
            # 创建原始记忆单元
            unit = MemoryUnit(
                memory_id=f"mu_{msg.message_id}",
                conversation_id=conversation_id,
                timestamp=msg.timestamp,
                content=msg.content,
                unit_type="conversation",
                metadata={
                    "role": msg.role,
                    "message_id": msg.message_id,
                    "embedding_only": True
                }
            )
            
            # 生成嵌入
            embedding = await self.embedding_manager.generate_embedding(
                msg.content,
                model=self.settings.models.default_embedding_model
            )
            unit.embedding = embedding
            embeddings_generated += 1
            
            memory_units.append(unit)
        
        return CompressionResult(
            memory_units=memory_units,
            embeddings_generated=embeddings_generated,
            compression_performed=False,
            trigger=CompressionTrigger(),
            cost=0.0,  # 将在外部计算
            metadata={
                "compression_type": "embedding_only",
                "model_used": self.settings.models.default_embedding_model
            }
        )
    
    async def _generate_comprehensive_summary(
        self,
        conversation_id: str,
        messages: List[MessageModel]
    ) -> List[MemoryUnit]:
        """生成全面总结"""
        # 构建提示
        conversation_text = self._format_messages(messages)
        prompt = f"""请为以下对话生成一个全面的总结，包括：

1. 主要讨论的技术主题和决策
2. 解决的问题和遇到的挑战
3. 重要的代码修改和架构变更
4. 关键的错误和解决方案
5. 待解决的问题和后续计划

对话内容：
{conversation_text}

要求：
- 保留所有技术细节和决策理由
- 使用结构化的格式
- 突出重要信息"""
        
        # 调用模型
        response = await self.model_manager.generate_completion(
            model=self.settings.memory.summary_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=self.settings.memory.summary_max_tokens
        )
        
        summary_content = response.get("content", "")
        
        # 创建全局记忆单元
        global_unit = MemoryUnit(
            memory_id=f"global_{conversation_id}_{datetime.now().timestamp()}",
            conversation_id=conversation_id,
            timestamp=datetime.now(),
            content=summary_content,
            unit_type="global_mu",
            metadata={
                "trigger": "manual_review",
                "message_count": len(messages),
                "model": self.settings.memory.summary_model
            }
        )
        
        return [global_unit]
    
    async def _generate_focused_summary(
        self,
        conversation_id: str,
        messages: List[MessageModel],
        keywords: List[str]
    ) -> List[MemoryUnit]:
        """生成重点总结"""
        conversation_text = self._format_messages(messages)
        keywords_str = ", ".join(keywords)
        
        prompt = f"""请为以下对话生成一个重点总结，特别关注与这些关键词相关的内容：{keywords_str}

对话内容：
{conversation_text}

要求：
- 重点提取与关键词相关的决策和讨论
- 保留相关的技术细节
- 简明扼要，突出重点"""
        
        response = await self.model_manager.generate_completion(
            model=self.settings.memory.summary_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        
        summary_content = response.get("content", "")
        
        # 创建快速记忆单元
        quick_unit = MemoryUnit(
            memory_id=f"quick_{conversation_id}_{datetime.now().timestamp()}",
            conversation_id=conversation_id,
            timestamp=datetime.now(),
            content=summary_content,
            unit_type="quick_mu",
            metadata={
                "trigger": "keyword",
                "keywords": keywords,
                "message_count": len(messages)
            }
        )
        
        return [quick_unit]
    
    async def _generate_standard_compression(
        self,
        conversation_id: str,
        messages: List[MessageModel]
    ) -> List[MemoryUnit]:
        """生成标准压缩"""
        # 分批处理消息
        batch_size = 10
        memory_units = []
        
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            conversation_text = self._format_messages(batch)
            
            prompt = f"""请提取以下对话的关键信息：

{conversation_text}

要求：
- 提取技术决策和重要信息
- 去除闲聊和重复内容
- 保持时间顺序"""
            
            response = await self.model_manager.generate_completion(
                model=self.settings.models.default_light_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500
            )
            
            content = response.get("content", "")
            
            if content:
                unit = MemoryUnit(
                    memory_id=f"batch_{conversation_id}_{i}_{datetime.now().timestamp()}",
                    conversation_id=conversation_id,
                    timestamp=batch[-1].timestamp,
                    content=content,
                    unit_type="conversation",
                    metadata={
                        "batch_index": i // batch_size,
                        "message_count": len(batch),
                        "compression": "standard"
                    }
                )
                memory_units.append(unit)
        
        return memory_units
    
    def _format_messages(self, messages: List[MessageModel]) -> str:
        """格式化消息"""
        lines = []
        for msg in messages:
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"[{timestamp}] {msg.role}: {msg.content}")
        return "\n".join(lines)
    
    def _filter_new_messages(
        self,
        messages: List[MessageModel]
    ) -> List[MessageModel]:
        """过滤新消息"""
        return [
            msg for msg in messages
            if msg.message_id not in self._processed_message_ids
        ]
    
    def _mark_messages_processed(self, messages: List[MessageModel]) -> None:
        """标记消息已处理"""
        for msg in messages:
            self._processed_message_ids.add(msg.message_id)
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._processed_message_ids.clear()
        logger.info("compressor_cache_cleared")
    
    async def get_compression_stats(self) -> Dict[str, Any]:
        """获取压缩统计"""
        return {
            "mode": self.settings.memory.default_memory_mode,
            "processed_messages": len(self._processed_message_ids),
            "auto_keywords": self.settings.memory.summary_auto_trigger_keywords,
            "total_cost": self.cost_tracker.get_total_cost()
        }