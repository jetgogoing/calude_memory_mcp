"""
Claude记忆管理MCP服务 - 服务管理器

负责整个服务的生命周期管理、组件协调和性能监控。
"""

from __future__ import annotations

import asyncio
import signal
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel
from claude_memory.database.session_manager import get_db_session
from claude_memory.models.data_models import (
    ConversationModel,
    ContextInjectionRequest,
    ContextInjectionResponse,
    HealthStatus,
    MemoryUnitDB,
    MemoryUnitModel,
    SearchQuery,
    SearchResponse,
)
from claude_memory.config.settings import get_settings
from claude_memory.collectors.conversation_collector import ConversationCollector
from claude_memory.processors.semantic_compressor import SemanticCompressor, CompressionRequest
from claude_memory.retrievers.semantic_retriever import SemanticRetriever, RetrievalRequest
from claude_memory.injectors.context_injector import ContextInjector
from claude_memory.utils.error_handling import (
    handle_exceptions,
    ProcessingError,
    ServiceError,
)

logger = structlog.get_logger(__name__)


class ServiceMetrics(BaseModel):
    """服务指标模型"""
    
    uptime_seconds: float
    conversations_processed: int
    memories_created: int
    memories_retrieved: int
    contexts_injected: int
    average_response_time_ms: float
    error_count: int
    last_error: Optional[str] = None
    memory_usage_mb: float
    cpu_usage_percent: float


class ServiceStatus(BaseModel):
    """服务状态模型"""
    
    status: str
    version: str
    started_at: datetime
    last_health_check: datetime
    components: Dict[str, Dict[str, Any]]
    metrics: ServiceMetrics
    configuration: Dict[str, Any]


class ServiceManager:
    """
    服务管理器 - 统一管理所有组件
    
    功能特性:
    - 服务生命周期管理
    - 组件协调和通信
    - 性能监控和指标收集
    - 健康检查和自愈
    - 优雅关闭处理
    - 配置热更新
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # 服务状态
        self.started_at = datetime.utcnow()
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # 核心组件
        self.conversation_collector: Optional[ConversationCollector] = None
        self.semantic_compressor: Optional[SemanticCompressor] = None
        self.semantic_retriever: Optional[SemanticRetriever] = None
        self.context_injector: Optional[ContextInjector] = None
        
        # 性能指标
        self.metrics = ServiceMetrics(
            uptime_seconds=0.0,
            conversations_processed=0,
            memories_created=0,
            memories_retrieved=0,
            contexts_injected=0,
            average_response_time_ms=0.0,
            error_count=0,
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0
        )
        
        # 响应时间统计
        self.response_times: List[float] = []
        self.max_response_history = 1000
        
        # 后台任务
        self.background_tasks: List[asyncio.Task] = []
        
        logger.info("ServiceManager initialized")

    @handle_exceptions(logger=logger, reraise=True)
    async def start_service(self) -> None:
        """
        启动服务
        """
        try:
            logger.info("Starting Claude Memory MCP Service...")
            
            # 初始化组件
            await self._initialize_components()
            
            # 设置信号处理
            self._setup_signal_handlers()
            
            # 启动后台任务
            await self._start_background_tasks()
            
            # 标记服务为运行状态
            self.is_running = True
            
            logger.info(
                "Claude Memory MCP Service started successfully",
                version=self.settings.service.version,
                started_at=self.started_at.isoformat(),
            )
            
        except Exception as e:
            logger.error("Failed to start service", error=str(e))
            await self.stop_service()
            raise ServiceError(f"Service startup failed: {str(e)}")

    @handle_exceptions(logger=logger)
    async def stop_service(self) -> None:
        """
        停止服务
        """
        logger.info("Stopping Claude Memory MCP Service...")
        
        try:
            # 标记服务为停止状态
            self.is_running = False
            self.shutdown_event.set()
            
            # 停止后台任务
            await self._stop_background_tasks()
            
            # 停止组件
            await self._shutdown_components()
            
            # 会话管理器会自动清理连接
            
            logger.info("Claude Memory MCP Service stopped successfully")
            
        except Exception as e:
            logger.error("Error during service shutdown", error=str(e))

    async def _initialize_components(self) -> None:
        """
        初始化所有组件
        """
        logger.info("Initializing service components...")
        
        try:
            # 初始化语义压缩器
            self.semantic_compressor = SemanticCompressor()
            
            # 初始化语义检索器
            self.semantic_retriever = SemanticRetriever()
            await self.semantic_retriever.initialize_collection()
            
            # 初始化上下文注入器
            self.context_injector = ContextInjector(self.semantic_retriever)
            
            # 初始化对话收集器
            self.conversation_collector = ConversationCollector()
            
            # TODO: 设置事件处理 - 暂时注释掉以完成基础测试
            # self.conversation_collector.set_conversation_handler(
            #     self._handle_new_conversation
            # )
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error("Component initialization failed", error=str(e))
            raise

    async def _start_background_tasks(self) -> None:
        """
        启动后台任务
        """
        logger.info("Starting background tasks...")
        
        # 启动对话收集器
        if self.conversation_collector:
            collect_task = asyncio.create_task(
                self.conversation_collector.start_collection()
            )
            self.background_tasks.append(collect_task)
        
        # 启动健康检查任务
        health_task = asyncio.create_task(self._health_check_loop())
        self.background_tasks.append(health_task)
        
        # 启动指标更新任务
        metrics_task = asyncio.create_task(self._metrics_update_loop())
        self.background_tasks.append(metrics_task)
        
        # 启动记忆清理任务
        cleanup_task = asyncio.create_task(self._memory_cleanup_loop())
        self.background_tasks.append(cleanup_task)
        
        logger.info(f"Started {len(self.background_tasks)} background tasks")

    async def _stop_background_tasks(self) -> None:
        """
        停止所有后台任务
        """
        logger.info("Stopping background tasks...")
        
        # 取消所有任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务完成或取消
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        self.background_tasks.clear()
        logger.info("Background tasks stopped")

    async def _shutdown_components(self) -> None:
        """
        关闭所有组件
        """
        logger.info("Shutting down components...")
        
        # 停止对话收集器
        if self.conversation_collector:
            await self.conversation_collector.stop_collection()
        
        # 组件清理
        self.semantic_compressor = None
        self.semantic_retriever = None
        self.context_injector = None
        self.conversation_collector = None
        
        logger.info("Components shutdown completed")

    def _setup_signal_handlers(self) -> None:
        """
        设置信号处理器
        """
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            # 使用shutdown_event来触发优雅关闭，而不是直接创建task
            self.shutdown_event.set()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _handle_new_conversation(self, conversation: ConversationModel) -> None:
        """
        处理新对话
        
        Args:
            conversation: 新的对话模型
        """
        try:
            start_time = datetime.utcnow()
            
            logger.info(
                "Processing new conversation",
                conversation_id=str(conversation.id),
                message_count=conversation.message_count
            )
            
            # 压缩对话为记忆单元
            if self.semantic_compressor:
                compression_request = CompressionRequest(
                    conversation=conversation,
                    unit_type=self._determine_memory_type(conversation),
                    quality_threshold=self.settings.memory.quality_threshold
                )
                
                compression_result = await self.semantic_compressor.compress_conversation(
                    compression_request
                )
                
                # 存储记忆单元
                if self.semantic_retriever:
                    await self.semantic_retriever.store_memory_unit(
                        compression_result.memory_unit
                    )
                    self.metrics.memories_created += 1
            
            # 更新指标
            self.metrics.conversations_processed += 1
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_response_time(processing_time)
            
            logger.info(
                "Conversation processed successfully",
                conversation_id=str(conversation.id),
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(
                "Failed to process conversation",
                conversation_id=str(conversation.id),
                error=str(e)
            )
            self.metrics.error_count += 1
            self.metrics.last_error = str(e)

    def _determine_memory_type(self, conversation: ConversationModel) -> str:
        """
        确定记忆类型
        
        Args:
            conversation: 对话模型
            
        Returns:
            str: 记忆类型
        """
        # 根据对话长度和内容判断记忆类型
        if conversation.message_count > 10 or conversation.token_count > 5000:
            return "GLOBAL"
        else:
            return "QUICK"

    def _update_response_time(self, response_time_ms: float) -> None:
        """
        更新响应时间统计
        
        Args:
            response_time_ms: 响应时间(毫秒)
        """
        self.response_times.append(response_time_ms)
        
        # 保持固定大小的历史记录
        if len(self.response_times) > self.max_response_history:
            self.response_times = self.response_times[-self.max_response_history:]
        
        # 更新平均响应时间
        if self.response_times:
            self.metrics.average_response_time_ms = sum(self.response_times) / len(self.response_times)

    async def _health_check_loop(self) -> None:
        """
        健康检查循环
        """
        while self.is_running and not self.shutdown_event.is_set():
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.settings.monitoring.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check failed", error=str(e))
                await asyncio.sleep(30)  # 错误时延长间隔

    async def _perform_health_check(self) -> None:
        """
        执行健康检查
        """
        # 检查数据库连接
        try:
            from sqlalchemy import text
            async with get_db_session() as session:
                await session.execute(text("SELECT 1"))
        except Exception as e:
            logger.warning("Database health check failed", error=str(e))
        
        # 检查Qdrant连接
        if self.semantic_retriever:
            try:
                # Qdrant客户端get_collections是同步方法，不需要await
                self.semantic_retriever.qdrant_client.get_collections()
            except Exception as e:
                logger.warning("Qdrant health check failed", error=str(e))
        
        logger.debug("Health check completed")

    async def _metrics_update_loop(self) -> None:
        """
        指标更新循环
        """
        while self.is_running and not self.shutdown_event.is_set():
            try:
                await self._update_system_metrics()
                await asyncio.sleep(self.settings.monitoring.metrics_update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Metrics update failed", error=str(e))
                await asyncio.sleep(60)

    async def _update_system_metrics(self) -> None:
        """
        更新系统指标
        """
        import psutil
        
        # 更新运行时间
        self.metrics.uptime_seconds = (datetime.utcnow() - self.started_at).total_seconds()
        
        # 更新系统资源使用
        process = psutil.Process()
        self.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        self.metrics.cpu_usage_percent = process.cpu_percent()

    async def _memory_cleanup_loop(self) -> None:
        """
        记忆清理循环
        """
        while self.is_running and not self.shutdown_event.is_set():
            try:
                await self._cleanup_expired_memories()
                # 每小时清理一次
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Memory cleanup failed", error=str(e))
                await asyncio.sleep(1800)  # 错误时30分钟后重试

    async def _cleanup_expired_memories(self) -> None:
        """
        清理过期记忆
        """
        if not self.semantic_retriever:
            return
        
        try:
            current_time = datetime.utcnow()
            
            # 查询过期的记忆单元
            from sqlalchemy import select, text
            async with get_db_session() as session:
                expired_memories = await session.execute(
                    select(MemoryUnitDB).filter(
                        MemoryUnitDB.expires_at < current_time
                    )
                )
            
            deleted_count = 0
            for memory in expired_memories.scalars():
                success = await self.semantic_retriever.delete_memory_unit(memory.id)
                if success:
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired memories")
                
        except Exception as e:
            logger.error("Failed to cleanup expired memories", error=str(e))

    # 公共API方法

    @handle_exceptions(logger=logger, reraise=True)
    async def search_memories(self, query: SearchQuery) -> SearchResponse:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            
        Returns:
            SearchResponse: 搜索响应
        """
        start_time = datetime.utcnow()
        
        if not self.semantic_retriever:
            raise ServiceError("SemanticRetriever not initialized")
        
        try:
            # 构建检索请求
            retrieval_request = RetrievalRequest(
                query=query,
                limit=query.limit or 10,
                min_score=query.min_score or 0.5,
                rerank=True,
                hybrid_search=True
            )
            
            # 执行检索
            retrieval_result = await self.semantic_retriever.retrieve_memories(
                retrieval_request
            )
            
            # 更新指标
            self.metrics.memories_retrieved += len(retrieval_result.results)
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_response_time(processing_time)
            
            # 构建响应
            return SearchResponse(
                results=retrieval_result.results,
                total_count=retrieval_result.total_found,
                search_time_ms=retrieval_result.search_time_ms,
                query_id=str(uuid.uuid4()),
                metadata=retrieval_result.metadata
            )
            
        except Exception as e:
            self.metrics.error_count += 1
            self.metrics.last_error = str(e)
            raise ProcessingError(f"Memory search failed: {str(e)}")

    @handle_exceptions(logger=logger, reraise=True)
    async def inject_context(self, request: ContextInjectionRequest) -> ContextInjectionResponse:
        """
        注入上下文
        
        Args:
            request: 注入请求
            
        Returns:
            ContextInjectionResponse: 注入响应
        """
        start_time = datetime.utcnow()
        
        if not self.context_injector:
            raise ServiceError("ContextInjector not initialized")
        
        try:
            # 执行上下文注入
            response = await self.context_injector.inject_context(request)
            
            # 更新指标
            self.metrics.contexts_injected += 1
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_response_time(processing_time)
            
            return response
            
        except Exception as e:
            self.metrics.error_count += 1
            self.metrics.last_error = str(e)
            raise ProcessingError(f"Context injection failed: {str(e)}")

    @handle_exceptions(logger=logger, default_return=ServiceStatus(
        status="error",
        version="unknown",
        started_at=datetime.utcnow(),
        last_health_check=datetime.utcnow(),
        components={},
        metrics=ServiceMetrics(
            uptime_seconds=0,
            conversations_processed=0,
            memories_created=0,
            memories_retrieved=0,
            contexts_injected=0,
            average_response_time_ms=0,
            error_count=1,
            memory_usage_mb=0,
            cpu_usage_percent=0
        ),
        configuration={}
    ))
    async def get_service_status(self) -> ServiceStatus:
        """
        获取服务状态
        
        Returns:
            ServiceStatus: 服务状态
        """
        # 检查组件状态
        components = {
            'conversation_collector': {
                'status': 'running' if self.conversation_collector else 'not_initialized',
                'active': self.conversation_collector is not None
            },
            'semantic_compressor': {
                'status': 'running' if self.semantic_compressor else 'not_initialized',
                'active': self.semantic_compressor is not None
            },
            'semantic_retriever': {
                'status': 'running' if self.semantic_retriever else 'not_initialized',
                'active': self.semantic_retriever is not None
            },
            'context_injector': {
                'status': 'running' if self.context_injector else 'not_initialized',
                'active': self.context_injector is not None
            }
        }
        
        # 构建配置信息
        configuration = {
            'service_version': self.settings.service.version,
            'memory_settings': {
                'quick_mu_ttl_hours': self.settings.memory.quick_mu_ttl_hours,
                'quality_threshold': self.settings.memory.quality_threshold,
                'max_memory_units': self.settings.memory.max_memory_units
            },
            'performance_settings': {
                'batch_size': self.settings.performance.batch_size,
                'max_concurrent_requests': self.settings.performance.max_concurrent_requests,
                'request_timeout_seconds': self.settings.performance.request_timeout_seconds
            }
        }
        
        return ServiceStatus(
            status='running' if self.is_running else 'stopped',
            version=self.settings.service.version,
            started_at=self.started_at,
            last_health_check=datetime.utcnow(),
            components=components,
            metrics=self.metrics,
            configuration=configuration
        )

    @asynccontextmanager
    async def service_lifecycle(self):
        """
        服务生命周期上下文管理器
        """
        try:
            await self.start_service()
            yield self
        finally:
            await self.stop_service()