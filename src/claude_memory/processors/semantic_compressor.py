"""
Claude记忆管理MCP服务 - 语义压缩器

负责将对话内容压缩成高质量的记忆单元(Memory Units)。
使用多模型协作策略生成和优化记忆内容。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

from claude_memory.models.data_models import (
    ConversationModel,
    MemoryUnitModel,
    MemoryUnitType,
    MessageType,
)
from claude_memory.config.settings import get_settings
from claude_memory.utils.text_processing import TextProcessor
from claude_memory.utils.error_handling import (
    handle_exceptions,
    with_retry,
    ProcessingError,
    RetryableError,
)

logger = structlog.get_logger(__name__)


class CompressionRequest(BaseModel):
    """压缩请求模型"""
    
    conversation: ConversationModel
    unit_type: MemoryUnitType = MemoryUnitType.CONVERSATION
    quality_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_summary_length: int = Field(default=500, ge=100, le=2000)
    include_context: bool = True
    preserve_entities: bool = True


class CompressionResult(BaseModel):
    """压缩结果模型"""
    
    memory_unit: MemoryUnitModel
    quality_score: float = Field(ge=0.0, le=1.0)
    compression_ratio: float = Field(ge=0.0, le=1.0)
    processing_time_ms: float = Field(ge=0.0)
    model_used: str
    metadata: Optional[Dict[str, Any]] = None


class SemanticCompressor:
    """
    语义压缩器 - 负责生成高质量记忆单元
    
    功能特性:
    - 多模型协作策略
    - 质量评估和验证
    - 智能模型选择
    - 批量处理优化
    - 成本控制
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.text_processor = TextProcessor()
        
        # 初始化模型管理器
        from claude_memory.utils.model_manager import ModelManager
        self.model_manager = ModelManager()
        
        # 模型配置
        self.light_models = ["deepseek-ai/DeepSeek-V2.5", "deepseek-r1"]
        self.heavy_models = ["gemini-2.5-pro", "claude-3.5-sonnet"]
        
        # 质量阈值
        self.quality_thresholds = {
            MemoryUnitType.CONVERSATION: 0.7,
            MemoryUnitType.ERROR_LOG: 0.6,
            MemoryUnitType.DECISION: 0.8,
            MemoryUnitType.CODE_SNIPPET: 0.7,
            MemoryUnitType.DOCUMENTATION: 0.8,
            MemoryUnitType.ARCHIVE: 0.5,
        }
        
        # 缓存
        self.compression_cache: Dict[str, CompressionResult] = {}
        self.max_cache_size = 1000
        
        logger.info(
            "SemanticCompressor initialized",
            light_models=self.light_models,
            heavy_models=self.heavy_models,
            quality_thresholds=self.quality_thresholds,
        )

    @handle_exceptions(logger=logger, reraise=True)
    @with_retry(max_attempts=3)
    async def compress_conversation(
        self, request: CompressionRequest
    ) -> CompressionResult:
        """
        压缩对话为记忆单元
        
        Args:
            request: 压缩请求
            
        Returns:
            CompressionResult: 压缩结果
        """
        start_time = datetime.utcnow()
        
        try:
            # 验证输入
            if not request.conversation.messages:
                raise ProcessingError("Empty conversation cannot be compressed")
            
            # 检查缓存
            cache_key = self._generate_cache_key(request)
            if cache_key in self.compression_cache:
                logger.debug("Using cached compression result", cache_key=cache_key)
                return self.compression_cache[cache_key]
            
            # 预处理对话
            processed_content = await self._preprocess_conversation(request.conversation)
            
            # 选择合适的模型
            model_name = await self._select_model(request.unit_type, processed_content)
            
            # 生成记忆单元
            memory_unit = await self._generate_memory_unit(
                request, processed_content, model_name
            )
            
            # 质量评估
            quality_score = await self._evaluate_quality(
                memory_unit, request.conversation, request.quality_threshold
            )
            
            # 如果质量不够，尝试使用更强的模型
            if (quality_score < request.quality_threshold and 
                model_name in self.light_models):
                
                logger.info(
                    "Quality below threshold, retrying with heavy model",
                    quality_score=quality_score,
                    threshold=request.quality_threshold,
                    original_model=model_name
                )
                
                heavy_model = self._get_best_heavy_model()
                memory_unit = await self._generate_memory_unit(
                    request, processed_content, heavy_model
                )
                quality_score = await self._evaluate_quality(
                    memory_unit, request.conversation, request.quality_threshold
                )
                model_name = heavy_model
            
            # 计算压缩比
            original_tokens = request.conversation.token_count
            compressed_tokens = memory_unit.token_count
            # 压缩比应该是压缩后相对于原始的比例，确保不超过1.0
            if original_tokens > 0:
                compression_ratio = min(compressed_tokens / original_tokens, 1.0)
            else:
                compression_ratio = 0.0
            
            # 处理时间
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 构建结果
            result = CompressionResult(
                memory_unit=memory_unit,
                quality_score=quality_score,
                compression_ratio=compression_ratio,
                processing_time_ms=processing_time,
                model_used=model_name,
                metadata={
                    'conversation_id': str(request.conversation.id),
                    'original_messages': len(request.conversation.messages),
                    'original_tokens': original_tokens,
                    'compressed_tokens': compressed_tokens,
                    'processing_timestamp': start_time.isoformat(),
                }
            )
            
            # 缓存结果
            await self._cache_result(cache_key, result)
            
            logger.info(
                "Conversation compressed successfully",
                conversation_id=str(request.conversation.id),
                unit_type=request.unit_type.value,
                quality_score=quality_score,
                compression_ratio=compression_ratio,
                model_used=model_name,
                processing_time_ms=processing_time,
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to compress conversation",
                conversation_id=str(request.conversation.id),
                error=str(e)
            )
            raise ProcessingError(f"Compression failed: {str(e)}")

    @handle_exceptions(logger=logger, default_return=[])
    async def batch_compress_conversations(
        self, requests: List[CompressionRequest]
    ) -> List[CompressionResult]:
        """
        批量压缩对话
        
        Args:
            requests: 压缩请求列表
            
        Returns:
            List[CompressionResult]: 压缩结果列表
        """
        if not requests:
            return []
        
        batch_size = self.settings.performance.batch_size
        results = []
        
        # 分批处理
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            
            # 并发处理一批
            batch_tasks = [
                self.compress_conversation(request)
                for request in batch
            ]
            
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error("Batch compression error", error=str(result))
                    else:
                        results.append(result)
                        
            except Exception as e:
                logger.error("Batch processing failed", error=str(e))
        
        logger.info(
            "Batch compression completed",
            total_requests=len(requests),
            successful_results=len(results),
            success_rate=len(results) / len(requests) if requests else 0
        )
        
        return results

    async def _preprocess_conversation(self, conversation: ConversationModel) -> str:
        """
        预处理对话内容
        
        Args:
            conversation: 对话模型
            
        Returns:
            str: 预处理后的内容
        """
        processed_parts = []
        
        for message in conversation.messages:
            # 清理消息内容
            clean_content = await self.text_processor.clean_and_normalize(message.content)
            
            if not clean_content:
                continue
            
            # 添加消息类型标识
            if message.message_type == MessageType.HUMAN:
                processed_parts.append(f"[USER]: {clean_content}")
            elif message.message_type == MessageType.ASSISTANT:
                processed_parts.append(f"[ASSISTANT]: {clean_content}")
            elif message.message_type == MessageType.SYSTEM:
                processed_parts.append(f"[SYSTEM]: {clean_content}")
            else:
                processed_parts.append(f"[{message.message_type.value.upper()}]: {clean_content}")
        
        return "\n\n".join(processed_parts)

    async def _select_model(self, unit_type: MemoryUnitType, content: str) -> str:
        """
        选择合适的模型
        
        Args:
            unit_type: 记忆单元类型
            content: 内容
            
        Returns:
            str: 选择的模型名称
        """
        content_length = len(content)
        token_count = await self.text_processor.count_tokens(content)
        
        # 根据记忆单元类型和内容复杂度选择模型
        if unit_type in [MemoryUnitType.CONVERSATION, MemoryUnitType.ERROR_LOG]:
            # 对话和错误日志使用轻量模型
            if token_count < 2000:
                return self.light_models[0]  # deepseek-ai/DeepSeek-V2.5
            else:
                return self.light_models[1] if len(self.light_models) > 1 else self.light_models[0]
        
        elif unit_type in [MemoryUnitType.DECISION, MemoryUnitType.DOCUMENTATION]:
            # 决策和文档使用重型模型确保质量
            if token_count < 5000:
                return self.heavy_models[1] if len(self.heavy_models) > 1 else self.heavy_models[0]
            else:
                return self.heavy_models[0]
        
        else:  # CODE_SNIPPET, ARCHIVE
            # 归档类型使用轻量模型即可
            return self.light_models[0]

    def _get_best_heavy_model(self) -> str:
        """获取最佳重型模型"""
        # 这里可以根据当前API状态、成本等因素动态选择
        return self.heavy_models[0]  # gemini-2.5-pro

    async def _generate_memory_unit(
        self,
        request: CompressionRequest,
        content: str,
        model_name: str
    ) -> MemoryUnitModel:
        """
        生成记忆单元
        
        Args:
            request: 压缩请求
            content: 预处理后的内容
            model_name: 使用的模型名称
            
        Returns:
            MemoryUnitModel: 生成的记忆单元
        """
        # 构建提示词
        prompt = await self._build_compression_prompt(
            content, request.unit_type, request.max_summary_length
        )
        
        # 调用AI模型
        response = await self._call_ai_model(model_name, prompt)
        
        # 解析响应
        parsed_response = await self._parse_ai_response(response)
        
        # 提取关键词
        keywords = await self.text_processor.extract_keywords(
            parsed_response['summary'] + " " + parsed_response.get('content', ''),
            max_keywords=10
        )
        
        # 计算Token数量
        summary_tokens = await self.text_processor.count_tokens(parsed_response['summary'])
        content_tokens = await self.text_processor.count_tokens(parsed_response.get('content', ''))
        
        # 设置过期时间（仅对Quick-MU）
        # 计算过期时间 - 现在只有ARCHIVE类型会过期
        expires_at = None
        if request.unit_type == MemoryUnitType.ARCHIVE:
            expires_at = datetime.utcnow() + timedelta(
                days=self.settings.memory.retention_days
            )
        
        # 构建记忆单元
        memory_unit = MemoryUnitModel(
            id=str(uuid.uuid4()),  # 确保id是字符串
            project_id=request.conversation.project_id,  # 从对话继承project_id
            conversation_id=request.conversation.id,
            unit_type=request.unit_type,
            title=parsed_response.get('title', self._generate_auto_title(parsed_response['summary'])),
            summary=parsed_response['summary'],
            content=parsed_response.get('content', parsed_response['summary']),
            keywords=keywords,
            token_count=summary_tokens + content_tokens,
            metadata={
                'model_used': model_name,
                'compression_type': request.unit_type.value,
                'original_messages': len(request.conversation.messages),
                'source_session': request.conversation.session_id,
                'generation_timestamp': datetime.utcnow().isoformat(),
                'prompt_template': 'standard_compression_v1',
                'project_id': request.conversation.project_id,  # 在metadata中也记录
                **parsed_response.get('metadata', {})
            },
            expires_at=expires_at,
        )
        
        return memory_unit

    async def _build_compression_prompt(
        self,
        content: str,
        unit_type: MemoryUnitType,
        max_length: int
    ) -> str:
        """
        构建压缩提示词
        
        Args:
            content: 对话内容
            unit_type: 记忆单元类型
            max_length: 最大摘要长度
            
        Returns:
            str: 构建的提示词
        """
        base_prompt = f"""请分析以下对话内容，生成一个高质量的记忆摘要。

对话内容：
{content}

任务要求：
1. 生成一个不超过{max_length}字符的准确摘要
2. 保留关键信息、重要观点和结论
3. 识别讨论的主题和上下文
4. 记录重要的决策、计划或行动项
5. 保持原对话的核心含义和价值

"""
        
        if unit_type == MemoryUnitType.CONVERSATION:
            base_prompt += """记忆类型：快速记忆单元
重点关注：
- 当前会话的即时信息
- 用户的直接需求和问题
- 助手的直接回应和建议
- 短期相关的上下文信息

"""
        elif unit_type == MemoryUnitType.DOCUMENTATION:
            base_prompt += """记忆类型：全局记忆单元
重点关注：
- 深层的知识和见解
- 长期有价值的信息
- 重要的决策和结论
- 可能影响未来对话的关键信息
- 用户的偏好和行为模式

"""
        else:  # ARCHIVE
            base_prompt += """记忆类型：归档记忆单元
重点关注：
- 历史信息的保存
- 完整对话的精炼版本
- 重要事件的记录

"""
        
        base_prompt += """请以JSON格式返回结果：
{
    "title": "简短的标题（不超过50字符）",
    "summary": "详细摘要（不超过指定长度）",
    "content": "可选的额外内容（重要细节）",
    "key_topics": ["主题1", "主题2", "主题3"],
    "importance_score": 0.8,
    "metadata": {
        "main_intent": "对话的主要意图",
        "outcome": "对话的结果或结论",
        "action_items": ["行动项1", "行动项2"]
    }
}

记忆摘要："""
        
        return base_prompt

    async def _call_ai_model(self, model_name: str, prompt: str) -> str:
        """
        调用AI模型
        
        Args:
            model_name: 模型名称
            prompt: 提示词
            
        Returns:
            str: 模型响应
        """
        # 这里需要实现实际的模型调用逻辑
        # 临时返回模拟响应
        
        logger.debug(
            "Calling AI model for compression",
            model=model_name,
            prompt_length=len(prompt)
        )
        
        # 模拟AI响应
        mock_response = {
            "title": "对话摘要",
            "summary": "这是一个关于Claude记忆管理系统的技术讨论，涵盖了架构设计、实现细节和优化策略。",
            "content": "详细讨论了RAG架构、多模型协作、成本控制等关键技术点。",
            "key_topics": ["技术架构", "记忆管理", "系统设计"],
            "importance_score": 0.8,
            "metadata": {
                "main_intent": "技术讨论和方案设计",
                "outcome": "确定了系统架构和实现方案",
                "action_items": ["实现数据采集层", "优化性能指标"]
            }
        }
        
        return json.dumps(mock_response, ensure_ascii=False)

    async def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """
        解析AI响应
        
        Args:
            response: AI响应文本
            
        Returns:
            Dict[str, Any]: 解析后的数据
        """
        try:
            # 尝试解析JSON
            if response.strip().startswith('{'):
                return json.loads(response)
            
            # 如果不是JSON，尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # 如果都失败了，创建基本结构
            return {
                'title': 'Generated Summary',
                'summary': response[:500],  # 截取前500字符作为摘要
                'content': response,
                'key_topics': [],
                'importance_score': 0.7,
                'metadata': {}
            }
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse AI response as JSON", error=str(e))
            return {
                'title': 'Generated Summary',
                'summary': response[:500],
                'content': response,
                'key_topics': [],
                'importance_score': 0.7,
                'metadata': {'parse_error': str(e)}
            }

    def _generate_auto_title(self, summary: str) -> str:
        """
        自动生成标题
        
        Args:
            summary: 摘要内容
            
        Returns:
            str: 生成的标题
        """
        # 提取前50个字符作为标题
        title = summary[:50].strip()
        
        # 确保在单词边界截断
        if len(title) < len(summary):
            last_space = title.rfind(' ')
            if last_space > 20:  # 确保标题不会太短
                title = title[:last_space]
            title += "..."
        
        return title

    @handle_exceptions(logger=logger, reraise=True)
    async def _generate_memory_unit(
        self,
        request: CompressionRequest,
        processed_content: str,
        model_name: str
    ) -> MemoryUnitModel:
        """
        生成记忆单元
        
        Args:
            request: 压缩请求
            processed_content: 预处理后的内容
            model_name: 使用的模型名称
            
        Returns:
            MemoryUnitModel: 生成的记忆单元
        """
        try:
            # 构建压缩提示
            compression_prompt = await self._build_compression_prompt(
                processed_content,
                request.unit_type,
                request.max_summary_length
            )
            
            # 使用模型管理器生成摘要
            # 生成压缩结果
            completion_result = await self.model_manager.generate_completion(
                model=model_name,
                messages=[{"role": "user", "content": compression_prompt}],
                max_tokens=request.max_summary_length * 2,
                temperature=0.3
            )
            
            # 解析结果
            summary_text = completion_result.content.strip()
            
            # 生成标题
            title = self._generate_auto_title(summary_text)
            
            # 提取关键词 - 简单实现
            keywords = await self.text_processor.extract_keywords(
                summary_text + " " + processed_content
            )
            
            # 计算过期时间 - 现在只有ARCHIVE类型会过期
            expires_at = None
            if request.unit_type == MemoryUnitType.ARCHIVE:
                expires_at = datetime.utcnow() + timedelta(
                    days=self.settings.memory.retention_days
                )
            
            # 构建记忆单元
            memory_unit = MemoryUnitModel(
                id=str(uuid.uuid4()),
                project_id=request.conversation.project_id,  # 从对话继承project_id
                conversation_id=request.conversation.id,
                unit_type=request.unit_type,
                title=title,
                summary=summary_text,
                content=processed_content[:2000],  # 限制内容长度
                keywords=keywords[:10],  # 限制关键词数量
                token_count=len(summary_text.split()),
                created_at=datetime.utcnow(),
                expires_at=expires_at,
                metadata={
                    'model_used': model_name,
                    'compression_version': '1.4',
                    'project_id': request.conversation.project_id,  # 在metadata中也记录
                    'original_length': len(processed_content),
                    'compression_ratio': min(len(summary_text) / len(processed_content), 1.0) if processed_content else 0,
                    'message_count': request.conversation.message_count,
                    'importance_score': 0.5,  # 默认重要性分数
                    'quality_score': 0.0  # 将在质量评估后更新
                }
            )
            
            return memory_unit
            
        except Exception as e:
            logger.error(
                "Failed to generate memory unit",
                model_name=model_name,
                unit_type=request.unit_type.value,
                content_length=len(processed_content),
                error=str(e)
            )
            raise ProcessingError(f"Memory unit generation failed: {str(e)}")

    async def _evaluate_quality(
        self,
        memory_unit: MemoryUnitModel,
        original_conversation: ConversationModel,
        threshold: float
    ) -> float:
        """
        评估记忆单元质量
        
        Args:
            memory_unit: 记忆单元
            original_conversation: 原始对话
            threshold: 质量阈值
            
        Returns:
            float: 质量分数 (0-1)
        """
        quality_factors = []
        
        # 1. 长度合理性检查
        summary_length = len(memory_unit.summary)
        if 100 <= summary_length <= 2000:
            length_score = 1.0
        elif summary_length < 100:
            length_score = summary_length / 100
        else:
            length_score = max(0.5, 2000 / summary_length)
        quality_factors.append(length_score)
        
        # 2. 内容有意义性检查
        meaningful_score = 1.0 if await self.text_processor.is_content_meaningful(
            memory_unit.summary
        ) else 0.3
        quality_factors.append(meaningful_score)
        
        # 3. 关键词覆盖率
        if memory_unit.keywords:
            keyword_score = min(1.0, len(memory_unit.keywords) / 5)  # 理想是5个关键词
        else:
            keyword_score = 0.3
        quality_factors.append(keyword_score)
        
        # 4. 压缩比合理性
        if original_conversation.token_count > 0:
            compression_ratio = memory_unit.token_count / original_conversation.token_count
            if 0.1 <= compression_ratio <= 0.5:  # 理想压缩比
                compression_score = 1.0
            elif compression_ratio < 0.1:
                compression_score = compression_ratio / 0.1
            else:
                compression_score = max(0.3, 0.5 / compression_ratio)
        else:
            compression_score = 0.5
        quality_factors.append(compression_score)
        
        # 5. 结构完整性
        structure_score = 0.0
        if memory_unit.title and len(memory_unit.title.strip()) > 5:
            structure_score += 0.3
        if memory_unit.summary and len(memory_unit.summary.strip()) > 50:
            structure_score += 0.4
        if memory_unit.keywords:
            structure_score += 0.3
        quality_factors.append(structure_score)
        
        # 计算加权平均质量分数
        weights = [0.2, 0.3, 0.15, 0.2, 0.15]  # 各因子的权重
        quality_score = sum(f * w for f, w in zip(quality_factors, weights))
        
        logger.debug(
            "Quality evaluation completed",
            memory_unit_id=str(memory_unit.id),
            quality_score=quality_score,
            threshold=threshold,
            factors={
                'length': length_score,
                'meaningful': meaningful_score,
                'keywords': keyword_score,
                'compression': compression_score,
                'structure': structure_score
            }
        )
        
        return quality_score

    def _generate_cache_key(self, request: CompressionRequest) -> str:
        """
        生成缓存键
        
        Args:
            request: 压缩请求
            
        Returns:
            str: 缓存键
        """
        # 基于对话内容和压缩参数生成哈希
        content_hash = hashlib.md5(
            str(request.conversation.id).encode() +
            request.unit_type.value.encode() +
            str(request.quality_threshold).encode() +
            str(request.max_summary_length).encode()
        ).hexdigest()
        
        return f"compression_{content_hash}"

    async def _cache_result(self, cache_key: str, result: CompressionResult) -> None:
        """
        缓存压缩结果
        
        Args:
            cache_key: 缓存键
            result: 压缩结果
        """
        # 控制缓存大小
        if len(self.compression_cache) >= self.max_cache_size:
            # 删除最旧的一半缓存
            old_keys = list(self.compression_cache.keys())[:self.max_cache_size // 2]
            for key in old_keys:
                del self.compression_cache[key]
        
        self.compression_cache[cache_key] = result

    async def generate_global_memory_review(
        self, conversations: List[ConversationModel], timeframe_days: int = 7
    ) -> MemoryUnitModel:
        """
        生成全局记忆回顾
        
        Args:
            conversations: 对话列表
            timeframe_days: 时间框架（天数）
            
        Returns:
            MemoryUnitModel: 全局记忆单元
        """
        if not conversations:
            raise ProcessingError("No conversations provided for global review")
        
        # 收集所有对话的摘要信息
        conversation_summaries = []
        total_messages = 0
        total_tokens = 0
        
        for conv in conversations:
            # 为每个对话生成快速摘要
            quick_request = CompressionRequest(
                conversation=conv,
                unit_type=MemoryUnitType.CONVERSATION,
                max_summary_length=200
            )
            
            quick_result = await self.compress_conversation(quick_request)
            conversation_summaries.append({
                'session_id': conv.session_id,
                'title': quick_result.memory_unit.title,
                'summary': quick_result.memory_unit.summary,
                'keywords': quick_result.memory_unit.keywords,
                'timestamp': conv.created_at.isoformat(),
                'message_count': conv.message_count,
                'token_count': conv.token_count
            })
            
            total_messages += conv.message_count
            total_tokens += conv.token_count
        
        # 构建全局回顾内容
        review_content = self._build_global_review_content(
            conversation_summaries, timeframe_days
        )
        
        # 生成全局记忆单元
        global_request = CompressionRequest(
            conversation=ConversationModel(
                session_id=f"global_review_{datetime.utcnow().isoformat()}",
                messages=[],  # 使用摘要内容而不是原始消息
                message_count=total_messages,
                token_count=total_tokens
            ),
            unit_type=MemoryUnitType.DOCUMENTATION,
            max_summary_length=1000
        )
        
        # 直接调用内部方法，使用构建的回顾内容
        model_name = await self._select_model(MemoryUnitType.DOCUMENTATION, review_content)
        global_memory = await self._generate_memory_unit(
            global_request, review_content, model_name
        )
        
        # 更新元数据
        global_memory.metadata.update({
            'review_type': 'global_memory_review',
            'timeframe_days': timeframe_days,
            'conversations_count': len(conversations),
            'total_messages': total_messages,
            'total_tokens': total_tokens,
            'generation_method': 'aggregated_compression'
        })
        
        logger.info(
            "Global memory review generated",
            timeframe_days=timeframe_days,
            conversations_count=len(conversations),
            total_messages=total_messages,
            review_length=len(global_memory.summary)
        )
        
        return global_memory

    def _build_global_review_content(
        self, summaries: List[Dict[str, Any]], timeframe_days: int
    ) -> str:
        """
        构建全局回顾内容
        
        Args:
            summaries: 对话摘要列表
            timeframe_days: 时间框架
            
        Returns:
            str: 构建的回顾内容
        """
        content_parts = [
            f"全局记忆回顾 - 过去{timeframe_days}天的对话分析\n",
            f"总计对话数量: {len(summaries)}\n",
            f"分析时间范围: {timeframe_days}天\n\n",
            "主要对话摘要:\n"
        ]
        
        for i, summary in enumerate(summaries, 1):
            content_parts.append(
                f"{i}. [{summary['timestamp'][:10]}] {summary['title']}\n"
                f"   摘要: {summary['summary']}\n"
                f"   关键词: {', '.join(summary['keywords'][:5])}\n"
                f"   消息数: {summary['message_count']}, Token数: {summary['token_count']}\n\n"
            )
        
        # 分析整体模式
        all_keywords = []
        for summary in summaries:
            all_keywords.extend(summary['keywords'])
        
        # 统计关键词频率
        keyword_freq = {}
        for keyword in all_keywords:
            keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
        
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        content_parts.append("整体趋势分析:\n")
        content_parts.append(f"高频主题: {', '.join([kw for kw, freq in top_keywords])}\n")
        content_parts.append(f"平均对话长度: {sum(s['message_count'] for s in summaries) / len(summaries):.1f}条消息\n")
        content_parts.append(f"平均Token使用: {sum(s['token_count'] for s in summaries) / len(summaries):.0f}个Token\n")
        
        return "".join(content_parts)
    
    async def close(self) -> None:
        """关闭资源"""
        try:
            if hasattr(self, 'model_manager') and self.model_manager:
                await self.model_manager.close()
                logger.info("SemanticCompressor model_manager closed")
        except Exception as e:
            logger.warning(f"Error closing SemanticCompressor resources: {e}")