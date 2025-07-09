"""
Claude记忆管理MCP服务 - Mini LLM 管理器

提供本地小模型和API模型的统一管理接口，优化推理性能和成本。
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from pydantic import BaseModel, Field

from ..config.settings import get_settings
from ..utils.error_handling import handle_exceptions, ProcessingError

logger = structlog.get_logger(__name__)


class TaskType(str, Enum):
    """任务类型枚举"""
    
    CLASSIFICATION = "classification"      # 分类任务
    SUMMARIZATION = "summarization"       # 摘要任务
    EXTRACTION = "extraction"             # 信息提取
    EMBEDDING = "embedding"               # 向量嵌入
    RERANKING = "reranking"              # 重排序
    COMPLETION = "completion"             # 通用补全


class ModelProvider(str, Enum):
    """模型提供商枚举"""
    
    LOCAL = "local"                      # 本地模型
    SILICONFLOW = "siliconflow"         # SiliconFlow API
    GEMINI = "gemini"                   # Gemini API
    OPENROUTER = "openrouter"           # OpenRouter API


class MiniLLMRequest(BaseModel):
    """Mini LLM 请求模型"""
    
    task_type: TaskType = Field(description="任务类型")
    input_text: Union[str, List[str], List[Dict[str, str]]] = Field(description="输入文本")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    model_hint: Optional[str] = Field(default=None, description="模型提示")
    use_cache: bool = Field(default=True, description="是否使用缓存")
    
    class Config:
        from_attributes = True


class MiniLLMResponse(BaseModel):
    """Mini LLM 响应模型"""
    
    task_type: TaskType = Field(description="任务类型")
    output: Any = Field(description="输出结果")
    model_used: str = Field(description="使用的模型")
    provider: ModelProvider = Field(description="模型提供商")
    latency_ms: float = Field(description="推理延迟（毫秒）")
    cached: bool = Field(default=False, description="是否从缓存返回")
    cost_usd: float = Field(default=0.0, description="成本（美元）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    class Config:
        from_attributes = True


class ModelProviderInterface(ABC):
    """模型提供商接口"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化提供商"""
        pass
    
    @abstractmethod
    async def process(self, request: MiniLLMRequest) -> MiniLLMResponse:
        """处理请求"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """检查是否可用"""
        pass
    
    @abstractmethod
    async def get_supported_tasks(self) -> List[TaskType]:
        """获取支持的任务类型"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理资源"""
        pass


class TaskRouter:
    """任务路由器"""
    
    def __init__(self, settings):
        self.settings = settings
        self.routing_rules = self._load_routing_rules()
        
    def _load_routing_rules(self) -> Dict[TaskType, Dict[str, Any]]:
        """加载路由规则"""
        # 获取提供商优先级
        provider_priority = self.settings.mini_llm.get_provider_priority_list()
        
        # 设置默认值
        if not provider_priority:
            provider_priority = ['siliconflow', 'openrouter', 'gemini']
        
        # 首选提供商和模型
        preferred_provider = provider_priority[0] if provider_priority else 'siliconflow'
        preferred_model = self.settings.mini_llm.get_model_for_provider(preferred_provider)
        
        # 默认路由规则，但COMPLETION任务使用配置
        default_rules = {
            TaskType.CLASSIFICATION: {
                "preferred_model": self.settings.models.default_light_model,
                "fallback_models": ["Qwen/Qwen2.5-1.5B-Instruct", "deepseek/deepseek-chat-v3-0324:free"],
                "max_tokens": 100,
                "temperature": 0.1,
                "provider": ModelProvider.SILICONFLOW
            },
            TaskType.SUMMARIZATION: {
                "preferred_model": self.settings.models.default_light_model,
                "fallback_models": ["Qwen/Qwen2.5-1.5B-Instruct", "deepseek/deepseek-chat-v3-0324:free"],
                "max_tokens": 500,
                "temperature": 0.3,
                "provider": ModelProvider.SILICONFLOW
            },
            TaskType.EXTRACTION: {
                "preferred_model": self.settings.models.default_light_model,
                "fallback_models": ["Qwen/Qwen2.5-1.5B-Instruct", "deepseek/deepseek-chat-v3-0324:free"],
                "max_tokens": 200,
                "temperature": 0.0,
                "provider": ModelProvider.SILICONFLOW
            },
            TaskType.EMBEDDING: {
                "preferred_model": self.settings.models.default_embedding_model,
                "fallback_models": ["text-embedding-004"],
                "provider": ModelProvider.SILICONFLOW
            },
            TaskType.RERANKING: {
                "preferred_model": self.settings.models.default_rerank_model,
                "fallback_models": [],
                "provider": ModelProvider.SILICONFLOW
            },
            TaskType.COMPLETION: {
                "preferred_model": preferred_model,
                "provider_priority": provider_priority,
                "max_tokens": self.settings.mini_llm.max_tokens,
                "temperature": self.settings.mini_llm.temperature,
                "provider": ModelProvider(preferred_provider)
            }
        }
        
        return default_rules
    
    def get_model_for_task(
        self,
        task_type: TaskType,
        available_models: Dict[str, List[str]]
    ) -> Optional[tuple[str, ModelProvider]]:
        """为任务选择最佳模型"""
        
        rules = self.routing_rules.get(task_type, {})
        preferred_model = rules.get("preferred_model")
        fallback_models = rules.get("fallback_models", [])
        
        # 尝试使用首选模型
        if preferred_model:
            for provider_name, models in available_models.items():
                if preferred_model in models:
                    provider = ModelProvider(provider_name.lower())
                    return preferred_model, provider
        
        # 尝试使用后备模型
        for fallback_model in fallback_models:
            for provider_name, models in available_models.items():
                if fallback_model in models:
                    provider = ModelProvider(provider_name.lower())
                    return fallback_model, provider
        
        # 没有找到合适的模型
        return None
    
    def get_task_parameters(self, task_type: TaskType) -> Dict[str, Any]:
        """获取任务默认参数"""
        rules = self.routing_rules.get(task_type, {})
        return {
            "max_tokens": rules.get("max_tokens", 500),
            "temperature": rules.get("temperature", 0.5),
            "top_p": rules.get("top_p", 0.9)
        }


class ResponseCache:
    """响应缓存"""
    
    def __init__(self, max_size_mb: int = 100, ttl_seconds: int = 3600):
        self.max_size_mb = max_size_mb
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple[MiniLLMResponse, datetime]] = {}
        self.access_count: Dict[str, int] = {}
        
    def _generate_key(self, request: MiniLLMRequest) -> str:
        """生成缓存键"""
        # 使用任务类型、输入文本和参数生成唯一键
        key_data = {
            "task_type": request.task_type,
            "input": request.input_text,
            "params": request.parameters
        }
        return json.dumps(key_data, sort_keys=True)
    
    async def get(self, request: MiniLLMRequest) -> Optional[MiniLLMResponse]:
        """从缓存获取响应"""
        if not request.use_cache:
            return None
            
        key = self._generate_key(request)
        
        if key in self.cache:
            response, timestamp = self.cache[key]
            
            # 检查是否过期
            if datetime.utcnow() - timestamp < timedelta(seconds=self.ttl_seconds):
                self.access_count[key] = self.access_count.get(key, 0) + 1
                
                # 标记为缓存命中
                cached_response = response.model_copy()
                cached_response.cached = True
                cached_response.latency_ms = 0.1  # 缓存访问延迟
                
                logger.info(
                    "Cache hit",
                    task_type=request.task_type,
                    access_count=self.access_count[key]
                )
                
                return cached_response
            else:
                # 清理过期缓存
                del self.cache[key]
                if key in self.access_count:
                    del self.access_count[key]
        
        return None
    
    async def set(self, request: MiniLLMRequest, response: MiniLLMResponse) -> None:
        """缓存响应"""
        if not request.use_cache:
            return
            
        key = self._generate_key(request)
        self.cache[key] = (response, datetime.utcnow())
        self.access_count[key] = 0
        
        # TODO: 实现基于大小的缓存清理
        await self._cleanup_if_needed()
    
    async def _cleanup_if_needed(self) -> None:
        """清理缓存（如果需要）"""
        # 简单实现：如果缓存项超过1000个，删除最少访问的项
        if len(self.cache) > 1000:
            # 按访问次数排序
            sorted_keys = sorted(
                self.access_count.keys(),
                key=lambda k: self.access_count.get(k, 0)
            )
            
            # 删除访问最少的20%
            to_remove = sorted_keys[:len(sorted_keys) // 5]
            for key in to_remove:
                if key in self.cache:
                    del self.cache[key]
                if key in self.access_count:
                    del self.access_count[key]
            
            logger.info(
                "Cache cleanup completed",
                removed_count=len(to_remove),
                remaining_count=len(self.cache)
            )


class MiniLLMManager:
    """
    Mini LLM 管理器
    
    统一管理本地模型和API模型，提供智能路由和缓存功能。
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.providers: Dict[ModelProvider, ModelProviderInterface] = {}
        self.task_router = TaskRouter(self.settings)
        self.response_cache = ResponseCache()
        self.initialized = False
        
        # 性能统计
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "provider_calls": {},
            "task_counts": {},
            "total_latency_ms": 0.0,
            "total_cost_usd": 0.0
        }
        
    async def initialize(self) -> None:
        """初始化管理器"""
        if self.initialized:
            return
            
        logger.info("Initializing MiniLLMManager...")
        
        # 初始化各个提供商
        await self._initialize_providers()
        
        self.initialized = True
        logger.info("MiniLLMManager initialized successfully")
    
    @handle_exceptions(logger=logger, reraise=True)
    async def process(self, request: MiniLLMRequest) -> MiniLLMResponse:
        """
        处理请求
        
        Args:
            request: Mini LLM 请求
            
        Returns:
            MiniLLMResponse: 处理结果
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        
        # 更新统计
        self.stats["total_requests"] += 1
        self.stats["task_counts"][request.task_type] = \
            self.stats["task_counts"].get(request.task_type, 0) + 1
        
        # 尝试从缓存获取
        cached_response = await self.response_cache.get(request)
        if cached_response:
            self.stats["cache_hits"] += 1
            return cached_response
        
        # 获取可用模型
        available_models = await self._get_available_models()
        
        # 选择模型
        model_info = self.task_router.get_model_for_task(
            request.task_type,
            available_models
        )
        
        if not model_info:
            raise ProcessingError(
                f"No suitable model found for task: {request.task_type}"
            )
        
        model_name, provider = model_info
        
        # 获取任务参数
        task_params = self.task_router.get_task_parameters(request.task_type)
        request.parameters.update(task_params)
        
        # 获取fallback提供商列表
        fallback_providers = None
        rules = self.task_router.routing_rules.get(request.task_type, {})
        if "fallback_providers" in rules:
            fallback_providers = rules["fallback_providers"]
        
        # 调用提供商处理请求
        response = await self._call_provider(provider, model_name, request, fallback_providers)
        
        # 更新统计
        latency_ms = (time.time() - start_time) * 1000
        response.latency_ms = latency_ms
        self.stats["total_latency_ms"] += latency_ms
        self.stats["total_cost_usd"] += response.cost_usd
        self.stats["provider_calls"][provider] = \
            self.stats["provider_calls"].get(provider, 0) + 1
        
        # 缓存响应
        await self.response_cache.set(request, response)
        
        logger.info(
            "Request processed",
            task_type=request.task_type,
            model=model_name,
            provider=provider,
            latency_ms=f"{latency_ms:.2f}",
            cost_usd=f"{response.cost_usd:.4f}"
        )
        
        return response
    
    async def _initialize_providers(self) -> None:
        """初始化所有提供商"""
        # 导入提供商类
        from .local_model_provider import LocalModelProvider
        from .api_model_provider import (
            SiliconFlowProvider,
            GeminiProvider,
            OpenRouterProvider
        )
        
        # 初始化本地模型提供商 - 暂时禁用，优先使用云服务
        # 用户要求：本地模型功能延后开发，优先级最低
        # if self.settings.mini_llm.local_models.enabled:
        #     try:
        #         local_provider = LocalModelProvider()
        #         await local_provider.initialize()
        #         if await local_provider.is_available():
        #             self.providers[ModelProvider.LOCAL] = local_provider
        #             logger.info("Local model provider initialized")
        #     except Exception as e:
        #         logger.error(f"Failed to initialize local model provider: {e}")
        
        # 初始化API提供商
        api_providers = [
            (ModelProvider.SILICONFLOW, SiliconFlowProvider),
            (ModelProvider.GEMINI, GeminiProvider),
            (ModelProvider.OPENROUTER, OpenRouterProvider)
        ]
        
        for provider_type, provider_class in api_providers:
            try:
                provider = provider_class()
                await provider.initialize()
                if await provider.is_available():
                    self.providers[provider_type] = provider
                    logger.info(f"{provider_type} provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize {provider_type} provider: {e}")
    
    async def _get_available_models(self) -> Dict[str, List[str]]:
        """获取可用模型列表"""
        available = {}
        
        for provider_type, provider in self.providers.items():
            try:
                # 获取支持的任务类型
                supported_tasks = await provider.get_supported_tasks()
                
                # 根据提供商类型获取模型列表
                # 暂时禁用本地模型
                # if provider_type == ModelProvider.LOCAL:
                #     from .local_model_provider import SUPPORTED_MODELS
                #     models = list(SUPPORTED_MODELS.keys())
                if provider_type == ModelProvider.SILICONFLOW:
                    from .api_model_provider import SiliconFlowProvider
                    models = list(SiliconFlowProvider.MODELS.keys())
                elif provider_type == ModelProvider.GEMINI:
                    from .api_model_provider import GeminiProvider
                    models = list(GeminiProvider.MODELS.keys())
                elif provider_type == ModelProvider.OPENROUTER:
                    from .api_model_provider import OpenRouterProvider
                    models = list(OpenRouterProvider.MODELS.keys())
                else:
                    models = []
                
                available[provider_type.value] = models
                
            except Exception as e:
                logger.error(f"Failed to get models from {provider_type}: {e}")
                available[provider_type.value] = []
        
        return available
    
    async def _call_provider(
        self,
        provider: ModelProvider,
        model_name: str,
        request: MiniLLMRequest,
        fallback_providers: Optional[List[str]] = None
    ) -> MiniLLMResponse:
        """调用提供商处理请求，支持自动fallback"""
        # 获取提供商优先级列表
        provider_priority = self.settings.mini_llm.get_provider_priority_list()
        
        # 确保主提供商在列表首位
        providers_to_try = []
        if provider.value in provider_priority:
            providers_to_try.append(provider)
            # 添加其他提供商作为fallback
            for p in provider_priority:
                if p != provider.value:
                    try:
                        providers_to_try.append(ModelProvider(p))
                    except ValueError:
                        logger.warning(f"Invalid provider in priority list: {p}")
        else:
            # 如果主提供商不在优先级列表中，使用完整的优先级列表
            for p in provider_priority:
                try:
                    providers_to_try.append(ModelProvider(p))
                except ValueError:
                    logger.warning(f"Invalid provider in priority list: {p}")
        
        # 记录所有错误，用于最终报告
        errors = []
        
        # 尝试每个提供商
        for idx, current_provider in enumerate(providers_to_try):
            if current_provider not in self.providers:
                error_msg = f"Provider {current_provider} not available"
                errors.append((current_provider, error_msg))
                logger.warning(error_msg)
                continue
            
            provider_instance = self.providers[current_provider]
            
            # 如果是fallback，需要选择合适的模型
            if idx > 0:  # 这是fallback提供商
                # 使用配置中指定的模型
                model_name = self.settings.mini_llm.get_model_for_provider(current_provider.value)
                
                logger.info(
                    "Attempting fallback",
                    fallback_provider=current_provider,
                    fallback_model=model_name,
                    attempt=idx + 1,
                    total_providers=len(providers_to_try)
                )
            
            # 设置模型提示
            request.model_hint = model_name
            
            # 尝试调用提供商
            try:
                response = await provider_instance.process(request)
                
                # 如果是fallback成功，记录
                if idx > 0:
                    logger.info(
                        "Fallback successful",
                        original_provider=provider,
                        fallback_provider=current_provider,
                        fallback_model=model_name,
                        attempt=idx + 1
                    )
                    # 更新响应元数据
                    response.metadata["fallback"] = True
                    response.metadata["fallback_provider"] = current_provider.value
                    response.metadata["fallback_attempt"] = idx + 1
                
                return response
                
            except Exception as e:
                error_msg = f"Provider {current_provider} failed: {str(e)}"
                errors.append((current_provider, str(e)))
                logger.error(
                    f"Provider {current_provider} failed",
                    error=str(e),
                    task_type=request.task_type,
                    model=model_name,
                    attempt=idx + 1,
                    remaining_providers=len(providers_to_try) - idx - 1
                )
                
                # 如果还有其他提供商可以尝试，继续
                if idx < len(providers_to_try) - 1:
                    continue
        
        # 所有提供商都失败了
        error_summary = "; ".join([f"{p}: {e}" for p, e in errors])
        raise ProcessingError(f"All providers failed. Errors: {error_summary}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 计算平均值
        if stats["total_requests"] > 0:
            stats["average_latency_ms"] = \
                stats["total_latency_ms"] / stats["total_requests"]
            stats["cache_hit_rate"] = \
                stats["cache_hits"] / stats["total_requests"]
            stats["average_cost_usd"] = \
                stats["total_cost_usd"] / stats["total_requests"]
        else:
            stats["average_latency_ms"] = 0.0
            stats["cache_hit_rate"] = 0.0
            stats["average_cost_usd"] = 0.0
        
        return stats
    
    async def cleanup(self) -> None:
        """清理资源"""
        logger.info("Cleaning up MiniLLMManager...")
        
        # 清理各个提供商
        for provider in self.providers.values():
            await provider.cleanup()
        
        self.initialized = False
        logger.info("MiniLLMManager cleanup completed")


# 全局实例
_mini_llm_manager: Optional[MiniLLMManager] = None


def get_mini_llm_manager() -> MiniLLMManager:
    """获取全局 Mini LLM 管理器实例"""
    global _mini_llm_manager
    if _mini_llm_manager is None:
        _mini_llm_manager = MiniLLMManager()
    return _mini_llm_manager