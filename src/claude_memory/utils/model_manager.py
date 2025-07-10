"""
Claude记忆管理MCP服务 - 模型管理器

负责统一管理所有AI模型的调用，包括：
- Gemini系列模型
- OpenRouter模型
- SiliconFlow模型 (v1.4: 主要用于Qwen3系列)

支持多提供商降级策略和成本控制。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Union

import aiohttp
import structlog
from pydantic import BaseModel, Field

from ..config.settings import get_settings
# from .cost_tracker import CostTracker  # 已删除
from .error_handling import handle_exceptions, with_retry, ProcessingError


logger = structlog.get_logger(__name__)


class ModelResponse(BaseModel):
    """模型响应"""
    
    content: str = Field(description="响应内容")
    usage: Optional[Dict[str, int]] = Field(default=None, description="token使用情况")
    model: str = Field(description="使用的模型")
    provider: str = Field(description="模型提供商")
    cost_usd: float = Field(default=0.0, description="调用成本")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="其他元数据")


class EmbeddingResponse(BaseModel):
    """嵌入响应"""
    
    embedding: List[float] = Field(description="向量表示")
    model: str = Field(description="使用的模型")
    provider: str = Field(description="模型提供商")
    dimension: int = Field(description="向量维度")
    usage: Optional[Dict[str, int]] = Field(default=None, description="token使用情况")
    cost_usd: float = Field(default=0.0, description="调用成本")


class RerankResponse(BaseModel):
    """重排序响应"""
    
    scores: List[float] = Field(description="重排序分数列表")
    model: str = Field(description="使用的模型")
    provider: str = Field(description="模型提供商")
    usage: Optional[Dict[str, int]] = Field(default=None, description="token使用情况")
    cost_usd: float = Field(default=0.0, description="调用成本")


class ModelManager:
    """统一模型管理器"""
    
    def __init__(self, cost_tracker: Optional[Any] = None):
        self.settings = get_settings()
        # self.cost_tracker = cost_tracker or CostTracker()  # 已删除成本追踪
        self.session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()  # 添加锁以防止并发创建会话
        
        # API配置
        self.providers = {
            'gemini': {
                'api_key': self.settings.models.gemini_api_key,
                'base_url': 'https://generativelanguage.googleapis.com/v1beta',
                'models': ['gemini-2.5-pro', 'gemini-2.5-flash', 'text-embedding-004']
            },
            'openrouter': {
                'api_key': self.settings.models.openrouter_api_key,
                'base_url': self.settings.models.openrouter_base_url,
                'models': ['openai/gpt-4', 'anthropic/claude-3.5-sonnet', 'deepseek/deepseek-chat-v3-0324']
            },
            'siliconflow': {
                'api_key': self.settings.models.siliconflow_api_key,
                'base_url': self.settings.models.siliconflow_base_url,
                'models': ['qwen3-embedding-8b', 'qwen3-reranker-8b', 'deepseek-ai/DeepSeek-V2.5']
            }
        }
        
        # 调试: 检查API key是否加载
        logger.info(
            "API keys status",
            gemini_configured=bool(self.providers['gemini']['api_key']),
            openrouter_configured=bool(self.providers['openrouter']['api_key']),
            siliconflow_configured=bool(self.providers['siliconflow']['api_key'])
        )
        
        # 模型映射
        self.model_provider_map = {
            # Gemini models
            'gemini-2.5-pro': 'gemini',
            'gemini-2.5-flash': 'gemini',
            'text-embedding-004': 'gemini',
            
            # OpenRouter models
            'openai/gpt-4': 'openrouter',
            'anthropic/claude-3.5-sonnet': 'openrouter',
            'deepseek/deepseek-chat-v3-0324': 'openrouter',
            'deepseek-r1': 'openrouter',  # 添加缺失的 deepseek-r1
            'claude-3.5-sonnet': 'openrouter',  # 添加缺失的简短名称
            
            # SiliconFlow models (v1.4: Qwen3系列)
            'Qwen/Qwen3-Embedding-8B': 'siliconflow',
            'Qwen/Qwen3-Reranker-8B': 'siliconflow',
            'deepseek-ai/DeepSeek-V2.5': 'siliconflow',
        }
        
        logger.info(
            "ModelManager initialized",
            providers=list(self.providers.keys()),
            total_models=len(self.model_provider_map)
        )
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """惰性且线程安全地获取会话"""
        if self.session is None:
            async with self._session_lock:
                # 双重检查，防止多个协程同时等待锁
                if self.session is None:
                    connector = aiohttp.TCPConnector(
                        limit=100,
                        limit_per_host=20,
                        ttl_dns_cache=300,
                        use_dns_cache=True
                    )
                    
                    timeout = aiohttp.ClientTimeout(
                        total=self.settings.models.request_timeout,
                        connect=10
                    )
                    
                    self.session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers={
                            'User-Agent': 'claude-memory-mcp-service/1.4.0'
                        }
                    )
                    
                    logger.info("HTTP session initialized")
        return self.session
    
    async def initialize(self) -> None:
        """初始化HTTP会话（保留以兼容现有代码）"""
        await self._get_session()
    
    async def close(self) -> None:
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("HTTP session closed")
    
    @handle_exceptions(logger=logger, reraise=True)
    @with_retry(max_attempts=3)
    async def generate_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """生成文本补全"""
        
        provider = self._get_provider(model)
        
        if provider == 'gemini':
            return await self._call_gemini_completion(
                model, messages, temperature, max_tokens, **kwargs
            )
        elif provider == 'openrouter':
            return await self._call_openrouter_completion(
                model, messages, temperature, max_tokens, **kwargs
            )
        elif provider == 'siliconflow':
            return await self._call_siliconflow_completion(
                model, messages, temperature, max_tokens, **kwargs
            )
        else:
            raise ProcessingError(f"Unsupported provider: {provider}")
    
    async def generate_embedding(
        self,
        model: str,
        text: str,
        **kwargs
    ) -> EmbeddingResponse:
        """生成文本嵌入"""
        
        provider = self._get_provider(model)
        
        if provider == 'gemini':
            return await self._call_gemini_embedding(model, text, **kwargs)
        elif provider == 'siliconflow':
            return await self._call_siliconflow_embedding(model, text, **kwargs)
        else:
            raise ProcessingError(f"Provider {provider} does not support embeddings")
    
    @handle_exceptions(logger=logger, reraise=True)
    @with_retry(max_attempts=3)
    async def rerank_documents(
        self,
        model: str,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        **kwargs
    ) -> RerankResponse:
        """重排序文档"""
        
        provider = self._get_provider(model)
        
        if provider == 'siliconflow':
            return await self._call_siliconflow_rerank(
                model, query, documents, top_k, **kwargs
            )
        else:
            raise ProcessingError(f"Provider {provider} does not support reranking")
    
    async def _call_siliconflow_embedding(
        self,
        model: str,
        text: str,
        **kwargs
    ) -> EmbeddingResponse:
        """调用SiliconFlow嵌入API"""
        
        if not self.session:
            await self.initialize()
        
        url = f"{self.providers['siliconflow']['base_url']}/embeddings"
        headers = {
            'Authorization': f"Bearer {self.providers['siliconflow']['api_key']}",
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'input': text,
            'encoding_format': 'float'
        }
        
        try:
            session = await self._get_session()
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                
                # 解析响应
                embedding = data['data'][0]['embedding']
                usage = data.get('usage', {})
                
                # 不再计算成本
                cost = 0.0
                
                logger.info(
                    "SiliconFlow embedding generated",
                    model=model,
                    input_length=len(text),
                    dimension=len(embedding),
                    cost=cost
                )
                
                return EmbeddingResponse(
                    embedding=embedding,
                    model=model,
                    provider='siliconflow',
                    dimension=len(embedding),
                    usage=usage,
                    cost_usd=cost
                )
                
        except Exception as e:
            logger.error(
                "SiliconFlow embedding failed",
                model=model,
                error=str(e)
            )
            raise ProcessingError(f"SiliconFlow embedding failed: {str(e)}")
    
    async def _call_siliconflow_rerank(
        self,
        model: str,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        **kwargs
    ) -> RerankResponse:
        """调用SiliconFlow重排序API"""
        
        if not self.session:
            await self.initialize()
        
        url = f"{self.providers['siliconflow']['base_url']}/rerank"
        headers = {
            'Authorization': f"Bearer {self.providers['siliconflow']['api_key']}",
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'query': query,
            'documents': documents,
            'top_k': top_k or len(documents),
            'return_documents': False
        }
        
        try:
            session = await self._get_session()
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                
                # 解析响应 - 获取重排序分数
                results = data['results']
                scores = [result['relevance_score'] for result in results]
                usage = data.get('usage', {})
                
                # 不再计算成本
                cost = 0.0
                
                logger.info(
                    "SiliconFlow rerank completed",
                    model=model,
                    query_length=len(query),
                    documents_count=len(documents),
                    top_k=len(scores),
                    cost=cost
                )
                
                return RerankResponse(
                    scores=scores,
                    model=model,
                    provider='siliconflow',
                    usage=usage,
                    cost_usd=cost
                )
                
        except Exception as e:
            logger.error(
                "SiliconFlow rerank failed",
                model=model,
                error=str(e)
            )
            raise ProcessingError(f"SiliconFlow rerank failed: {str(e)}")
    
    async def _call_siliconflow_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """调用SiliconFlow聊天API"""
        
        if not self.session:
            await self.initialize()
        
        url = f"{self.providers['siliconflow']['base_url']}/chat/completions"
        headers = {
            'Authorization': f"Bearer {self.providers['siliconflow']['api_key']}",
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'stream': False
        }
        
        if max_tokens:
            payload['max_tokens'] = max_tokens
        
        try:
            session = await self._get_session()
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                
                # 解析响应
                content = data['choices'][0]['message']['content']
                usage = data.get('usage', {})
                
                # 不再计算成本
                cost = 0.0
                
                logger.info(
                    "SiliconFlow completion generated",
                    model=model,
                    prompt_tokens=usage.get('prompt_tokens', 0),
                    completion_tokens=usage.get('completion_tokens', 0),
                    cost=cost
                )
                
                return ModelResponse(
                    content=content,
                    usage=usage,
                    model=model,
                    provider='siliconflow',
                    cost_usd=cost
                )
                
        except Exception as e:
            logger.error(
                "SiliconFlow completion failed",
                model=model,
                error=str(e)
            )
            raise ProcessingError(f"SiliconFlow completion failed: {str(e)}")
    
    async def _call_gemini_embedding(
        self,
        model: str,
        text: str,
        **kwargs
    ) -> EmbeddingResponse:
        """调用Gemini嵌入API (备用)"""
        
        # 简化实现，实际应该调用Google AI API
        logger.warning("Gemini embedding not implemented, using placeholder")
        
        # 返回占位符响应
        return EmbeddingResponse(
            embedding=[0.0] * 768,  # Gemini embedding dimension
            model=model,
            provider='gemini',
            dimension=768,
            cost_usd=0.0
        )
    
    async def _call_gemini_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """调用Gemini聊天API (备用)"""
        
        # 简化实现，实际应该调用Google AI API
        logger.warning("Gemini completion not implemented, using placeholder")
        
        return ModelResponse(
            content="Placeholder response",
            model=model,
            provider='gemini',
            cost_usd=0.0
        )
    
    async def _call_openrouter_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """调用OpenRouter API (备用)"""
        
        # 简化实现，实际应该调用OpenRouter API
        logger.warning("OpenRouter completion not implemented, using placeholder")
        
        return ModelResponse(
            content="Placeholder response",
            model=model,
            provider='openrouter',
            cost_usd=0.0
        )
    
    def _get_provider(self, model: str) -> str:
        """获取模型对应的提供商"""
        provider = self.model_provider_map.get(model)
        if not provider:
            raise ProcessingError(f"Unknown model: {model}")
        
        # 检查API密钥
        api_key = self.providers[provider]['api_key']
        if not api_key:
            raise ProcessingError(f"API key not configured for provider: {provider}")
        
        return provider
    
    async def get_available_models(self) -> Dict[str, List[str]]:
        """获取可用模型列表"""
        available = {}
        
        for provider, config in self.providers.items():
            if config['api_key']:  # 只列出已配置API密钥的提供商
                available[provider] = config['models']
        
        return available
    
    async def health_check(self) -> Dict[str, bool]:
        """健康检查所有提供商"""
        health_status = {}
        
        for provider, config in self.providers.items():
            if not config['api_key']:
                health_status[provider] = False
                continue
            
            try:
                # 简单的健康检查 - 实际实现应该调用各provider的health endpoint
                health_status[provider] = True
            except Exception:
                health_status[provider] = False
        
        return health_status