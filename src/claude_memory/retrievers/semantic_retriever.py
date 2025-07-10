"""
Claude记忆管理MCP服务 - 语义检索器

负责记忆单元的向量存储、语义搜索和相关性评分。
支持多种检索策略和重排序算法。
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import structlog
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import ResponseHandlingException
from sqlalchemy import and_, desc, func, or_
from claude_memory.database.session_manager import get_db_session
from claude_memory.models.data_models import (
    EmbeddingDB,
    MemoryUnitModel,
    MemoryUnitType,
    SearchQuery,
    SearchResult,
    SearchResponse,
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


class RetrievalRequest(BaseModel):
    """检索请求模型"""
    
    query: SearchQuery
    project_id: str = Field(default="global", description="项目ID，默认为global实现全局共享")
    limit: int = Field(default=50, ge=1, le=999999)  # 提升默认限制到50
    min_score: float = Field(default=0.2, ge=0.0, le=1.0)  # 降低相关性阈值
    include_expired: bool = False
    unit_types: Optional[List[MemoryUnitType]] = None
    rerank: bool = True
    hybrid_search: bool = True


class RetrievalResult(BaseModel):
    """检索结果模型"""
    
    results: List[SearchResult]
    total_found: int
    search_time_ms: float
    rerank_time_ms: Optional[float] = None
    retrieval_strategy: str
    metadata: Optional[Dict[str, Any]] = None


class SemanticRetriever:
    """
    语义检索器 - 负责高效的记忆检索
    
    功能特性:
    - 向量相似度搜索
    - 混合检索策略（语义+关键词）
    - 智能重排序算法
    - 过期记忆过滤
    - 缓存优化
    - 实时性能监控
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.text_processor = TextProcessor()
        
        # 初始化模型管理器
        from claude_memory.utils.model_manager import ModelManager
        self.model_manager = ModelManager()
        
        # 初始化Qdrant客户端
        # 从qdrant_url解析host和port
        url_parts = self.settings.qdrant.qdrant_url.replace("http://", "").replace("https://", "").split(":")
        host = url_parts[0]
        port = int(url_parts[1]) if len(url_parts) > 1 else 6333
        
        self.qdrant_client = AsyncQdrantClient(
            host=host,
            port=port,
            api_key=self.settings.qdrant.api_key,
            timeout=self.settings.qdrant.timeout,
            https=False,  # 禁用SSL，使用HTTP连接
            check_compatibility=False  # 禁用版本兼容性检查
        )
        
        # 集合名称
        self.collection_name = self.settings.qdrant.collection_name
        
        # 检索策略配置
        self.retrieval_strategies = {
            'semantic_only': self._semantic_search,
            'hybrid': self._hybrid_search,
            'keyword_only': self._keyword_search,
        }
        
        # 重排序算法
        self.rerank_algorithms = {
            'relevance_time': self._rerank_by_relevance_time,
            'quality_boost': self._rerank_by_quality_boost,
            'type_priority': self._rerank_by_type_priority,
        }
        
        # 缓存
        self.embedding_cache: Dict[str, np.ndarray] = {}
        self.search_cache: Dict[str, RetrievalResult] = {}
        self.max_cache_size = 500
        
        logger.info(
            "SemanticRetriever initialized",
            collection_name=self.collection_name,
            qdrant_url=self.settings.qdrant.qdrant_url,
            strategies=list(self.retrieval_strategies.keys()),
            rerank_algorithms=list(self.rerank_algorithms.keys())
        )

    @handle_exceptions(logger=logger, reraise=True)
    async def initialize_collection(self) -> None:
        """
        初始化Qdrant集合
        """
        try:
            # 检查集合是否存在
            collections = await self.qdrant_client.get_collections()
            collection_exists = any(
                col.name == self.collection_name for col in collections.collections
            )
            
            if not collection_exists:
                # 创建集合
                await self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qdrant_models.VectorParams(
                        size=self.settings.qdrant.vector_size,
                        distance=qdrant_models.Distance.COSINE
                    )
                )
                
                logger.info(
                    "Qdrant collection created",
                    collection_name=self.collection_name,
                    vector_size=self.settings.qdrant.vector_size
                )
            else:
                logger.info(
                    "Qdrant collection already exists",
                    collection_name=self.collection_name
                )
                
        except Exception as e:
            logger.error(
                "Failed to initialize Qdrant collection",
                collection_name=self.collection_name,
                error=str(e)
            )
            raise ProcessingError(f"Collection initialization failed: {str(e)}")

    @handle_exceptions(logger=logger, reraise=True)
    async def store_memory_unit(self, memory_unit: MemoryUnitModel) -> bool:
        """
        存储记忆单元到向量数据库
        
        Args:
            memory_unit: 记忆单元
            
        Returns:
            bool: 存储是否成功
        """
        try:
            # 生成嵌入向量
            embedding_vector = await self._generate_embedding(
                memory_unit.summary + " " + memory_unit.content
            )
            
            # 构建元数据
            metadata = {
                'id': str(memory_unit.id),
                'memory_unit_id': str(memory_unit.id),  # 添加memory_unit_id
                # 'project_id': memory_unit.project_id,    # 已删除：全局共享记忆
                'conversation_id': str(memory_unit.conversation_id),
                'unit_type': memory_unit.unit_type.value,
                'title': memory_unit.title,
                'keywords': memory_unit.keywords,
                'token_count': memory_unit.token_count,
                'created_at': memory_unit.created_at.timestamp(),
                'expires_at': memory_unit.expires_at.timestamp() if memory_unit.expires_at else None,
                'importance_score': memory_unit.metadata.get('importance_score', 0.5),
                'quality_score': memory_unit.metadata.get('quality_score', 0.5),
            }
            
            # 存储到Qdrant
            await self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[
                    qdrant_models.PointStruct(
                        id=str(memory_unit.id),
                        vector=embedding_vector.tolist(),
                        payload=metadata
                    )
                ]
            )
            
            # 同时存储嵌入记录到数据库
            logger.debug("Starting database storage for embedding")
            try:
                async with get_db_session() as session:
                    logger.debug("Database session obtained")
                    embedding_record = EmbeddingDB(
                        memory_unit_id=memory_unit.id,
                        vector=embedding_vector.tolist(),
                        model_name=self.settings.models.default_embedding_model,
                        dimension=len(embedding_vector)
                    )
                    logger.debug("EmbeddingDB record created")
                    
                    # 直接添加到会话，不保存返回值
                    session.add(embedding_record)
                    logger.debug("Record added to session")
                    # 提交事务 - 注意：commit()不返回任何值，所以不应该保存或等待它的结果
                    await session.commit()
                    logger.debug("Transaction committed successfully")
            except Exception as db_error:
                # 捕获数据库特定错误并提供更详细的信息
                logger.error(f"Database operation failed: {db_error}")
                logger.error(f"DB error type: {type(db_error)}")
                # 外键约束错误不应该被忽略，这表示数据不一致
                if "foreign key constraint" in str(db_error).lower():
                    logger.error("Foreign key constraint violation - memory unit must be saved to database first")
                    # 回滚向量存储以保持数据一致性
                    try:
                        await self.qdrant_client.delete(
                            collection_name=self.collection_name,
                            points_selector=qdrant_models.PointIdsList(
                                points=[str(memory_unit.id)]
                            )
                        )
                        logger.info("Rolled back vector storage due to database constraint violation")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback vector storage: {rollback_error}")
                    return False
                raise
            
            logger.info(
                "Memory unit stored successfully",
                memory_unit_id=str(memory_unit.id),
                vector_dimension=len(embedding_vector),
                unit_type=memory_unit.unit_type.value
            )
            
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to store memory unit {memory_unit.id}: {e}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            # 错误已在session上下文管理器中处理
            raise ProcessingError(f"Storage failed: {str(e)}")

    @handle_exceptions(logger=logger, default_return=RetrievalResult(results=[], total_found=0, search_time_ms=0.0, retrieval_strategy="error"))
    async def retrieve_memories(self, request: RetrievalRequest) -> RetrievalResult:
        """
        检索相关记忆
        
        Args:
            request: 检索请求
            
        Returns:
            RetrievalResult: 检索结果
        """
        start_time = datetime.utcnow()
        
        try:
            # 检查缓存
            cache_key = self._generate_search_cache_key(request)
            if cache_key in self.search_cache:
                logger.debug("Using cached search result", cache_key=cache_key)
                return self.search_cache[cache_key]
            
            # 选择检索策略
            strategy_name = self._select_retrieval_strategy(request)
            strategy_func = self.retrieval_strategies[strategy_name]
            
            # 执行检索
            search_results = await strategy_func(request)
            
            # 过滤过期记忆
            if not request.include_expired:
                search_results = await self._filter_expired_memories(search_results)
            
            # 重排序
            rerank_start_time = None
            rerank_time_ms = None
            
            if request.rerank and search_results:
                rerank_start_time = datetime.utcnow()
                search_results = await self._rerank_results(search_results, request.query)
                rerank_time_ms = (datetime.utcnow() - rerank_start_time).total_seconds() * 1000
            
            # 应用限制和分数阈值
            filtered_results = [
                result for result in search_results
                if result.relevance_score >= request.min_score
            ][:request.limit]
            
            # 计算处理时间
            search_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 构建结果
            result = RetrievalResult(
                results=filtered_results,
                total_found=len(search_results),
                search_time_ms=search_time_ms,
                rerank_time_ms=rerank_time_ms,
                retrieval_strategy=strategy_name,
                metadata={
                    'query_text': request.query.query,
                    'query_type': request.query.query_type,
                    'filters_applied': {
                        'min_score': request.min_score,
                        'include_expired': request.include_expired,
                        'unit_types': [ut.value for ut in request.unit_types] if request.unit_types else None,
                    },
                    'performance': {
                        'total_candidates': len(search_results),
                        'filtered_results': len(filtered_results),
                        'filter_ratio': len(filtered_results) / len(search_results) if search_results else 0,
                    }
                }
            )
            
            # 缓存结果
            await self._cache_search_result(cache_key, result)
            
            logger.info(
                "Memory retrieval completed",
                query_text=request.query.query[:50],
                strategy=strategy_name,
                total_found=len(search_results),
                returned_results=len(filtered_results),
                search_time_ms=search_time_ms,
                rerank_time_ms=rerank_time_ms,
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Memory retrieval failed",
                query_text=request.query.query[:50],
                error=str(e)
            )
            raise ProcessingError(f"Retrieval failed: {str(e)}")

    async def _semantic_search(self, request: RetrievalRequest) -> List[SearchResult]:
        """
        语义搜索
        
        Args:
            request: 检索请求
            
        Returns:
            List[SearchResult]: 搜索结果
        """
        # 生成查询向量
        query_vector = await self._generate_embedding(request.query.query)
        
        # 构建过滤条件
        query_filter = self._build_qdrant_filter(request)
        
        # 执行向量搜索
        search_results = await self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=request.limit * 2,  # 获取更多候选以便重排序
            query_filter=query_filter,
            with_payload=True,
            score_threshold=request.min_score * 0.8  # 略低的阈值，后续精确过滤
        )
        
        # 转换为SearchResult对象
        results = []
        for hit in search_results:
            # 从数据库获取完整的记忆单元信息
            memory_unit = await self._get_memory_unit_by_id(hit.payload['id'])
            if memory_unit:
                result = SearchResult(
                    memory_unit=memory_unit,
                    relevance_score=hit.score,
                    match_type='semantic',
                    matched_keywords=[],
                    metadata={
                        'vector_score': hit.score,
                        'distance': 1.0 - hit.score,  # 余弦距离
                    }
                )
                results.append(result)
        
        return results

    async def _hybrid_search(self, request: RetrievalRequest) -> List[SearchResult]:
        """
        混合搜索（语义+关键词）
        
        Args:
            request: 检索请求
            
        Returns:
            List[SearchResult]: 搜索结果
        """
        # 并行执行语义搜索和关键词搜索
        semantic_task = self._semantic_search(request)
        keyword_task = self._keyword_search(request)
        
        semantic_results, keyword_results = await asyncio.gather(
            semantic_task, keyword_task, return_exceptions=True
        )
        
        # 处理异常
        if isinstance(semantic_results, Exception):
            logger.warning("Semantic search failed in hybrid mode", error=str(semantic_results))
            semantic_results = []
        
        if isinstance(keyword_results, Exception):
            logger.warning("Keyword search failed in hybrid mode", error=str(keyword_results))
            keyword_results = []
        
        # 合并结果并去重
        combined_results = {}
        
        # 添加语义搜索结果
        for result in semantic_results:
            memory_id = str(result.memory_unit.id)
            combined_results[memory_id] = result
            combined_results[memory_id].match_type = 'semantic'
        
        # 合并关键词搜索结果
        for result in keyword_results:
            memory_id = str(result.memory_unit.id)
            if memory_id in combined_results:
                # 已存在，增强分数和匹配信息
                existing = combined_results[memory_id]
                existing.relevance_score = min(1.0, existing.relevance_score + result.relevance_score * 0.3)
                existing.match_type = 'hybrid'
                existing.matched_keywords.extend(result.matched_keywords)
                existing.metadata.update({'keyword_boost': True})
            else:
                # 新结果，添加到合并列表
                combined_results[memory_id] = result
                result.match_type = 'keyword'
        
        # 按相关性分数排序
        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x.relevance_score,
            reverse=True
        )
        
        return sorted_results

    async def _keyword_search(self, request: RetrievalRequest) -> List[SearchResult]:
        """
        关键词搜索
        
        Args:
            request: 检索请求
            
        Returns:
            List[SearchResult]: 搜索结果
        """
        # 提取查询关键词
        query_keywords = await self.text_processor.extract_keywords(
            request.query.query, max_keywords=20
        )
        
        if not query_keywords:
            return []
        
        # 构建数据库查询
        async with get_db_session() as session:
            from sqlalchemy import select
            from claude_memory.models.data_models import MemoryUnitDB
            query = select(MemoryUnitDB)
            
            # 项目ID过滤 - 支持全局共享
            # 对于全局共享模式，总是查询project_id="global"的记忆
            query = query.filter(MemoryUnitDB.project_id == "global")
            
            # 关键词匹配条件 - 修复JSON查询问题
            keyword_conditions = []
            for keyword in query_keywords:
                # 使用JSON操作符查询keywords数组
                keyword_conditions.append(
                    MemoryUnitDB.keywords.op('@>')([keyword])
                )
            
            # 应用关键词过滤
            if keyword_conditions:
                query = query.filter(or_(*keyword_conditions))
            
            # 应用类型过滤
            if request.unit_types:
                query = query.filter(MemoryUnitDB.unit_type.in_(request.unit_types))
            
            # 排除过期记忆
            if not request.include_expired:
                query = query.filter(
                    or_(
                        MemoryUnitDB.expires_at.is_(None),
                        MemoryUnitDB.expires_at > datetime.utcnow()
                    )
                )
            
            # 按创建时间降序排列
            query = query.order_by(desc(MemoryUnitDB.created_at))
            
            # 限制结果数量
            result = await session.execute(query.limit(request.limit * 2))
            memory_units = result.scalars().all()
        
        # 计算关键词匹配分数
        results = []
        for memory_unit in memory_units:
            matched_keywords = []
            match_score = 0.0
            
            # 检查关键词匹配
            for keyword in query_keywords:
                if keyword.lower() in [k.lower() for k in memory_unit.keywords]:
                    matched_keywords.append(keyword)
                    match_score += 1.0
                
                # 检查标题和摘要中的匹配
                if keyword.lower() in memory_unit.title.lower():
                    match_score += 0.5
                if keyword.lower() in memory_unit.summary.lower():
                    match_score += 0.3
            
            # 归一化分数
            relevance_score = min(1.0, match_score / len(query_keywords))
            
            if relevance_score >= request.min_score * 0.5:  # 较低的阈值用于关键词匹配
                # 转换MemoryUnitDB为MemoryUnitModel
                memory_unit_model = MemoryUnitModel(
                    memory_id=str(memory_unit.id),
                    project_id=memory_unit.project_id,
                    conversation_id=str(memory_unit.conversation_id),
                    unit_type=memory_unit.unit_type,
                    title=memory_unit.title,
                    summary=memory_unit.summary,
                    content=memory_unit.content,
                    keywords=memory_unit.keywords,
                    token_count=memory_unit.token_count,
                    created_at=memory_unit.created_at,
                    expires_at=memory_unit.expires_at,
                    metadata=memory_unit.metadata
                )
                
                result = SearchResult(
                    memory_unit=memory_unit_model,
                    relevance_score=relevance_score,
                    match_type='keyword',
                    matched_keywords=matched_keywords,
                    metadata={
                        'keyword_matches': len(matched_keywords),
                        'total_keywords': len(query_keywords),
                        'match_ratio': len(matched_keywords) / len(query_keywords) if query_keywords else 0,
                    }
                )
                results.append(result)
        
        return results

    async def _filter_expired_memories(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        过滤过期的记忆
        
        Args:
            results: 搜索结果列表
            
        Returns:
            List[SearchResult]: 过滤后的结果
        """
        current_time = datetime.utcnow()
        filtered_results = []
        
        for result in results:
            if (result.memory_unit.expires_at is None or 
                result.memory_unit.expires_at > current_time):
                filtered_results.append(result)
        
        return filtered_results

    async def _rerank_results(
        self, results: List[SearchResult], query: SearchQuery
    ) -> List[SearchResult]:
        """
        重排序搜索结果 (v1.4: 使用Qwen3-Reranker-8B)
        
        Args:
            results: 原始搜索结果 (Top-20)
            query: 搜索查询
            
        Returns:
            List[SearchResult]: 重排序后的结果 (Top-5)
        """
        if not results:
            return results
        
        try:
            # v1.4: 使用Qwen3-Reranker-8B进行智能重排序
            documents = [
                result.memory_unit.summary + " " + result.memory_unit.content
                for result in results
            ]
            
            # 调用ModelManager的重排序API
            try:
                rerank_response = await self.model_manager.rerank_documents(
                    model=self.settings.models.default_rerank_model,  # qwen3-reranker-8b
                    query=query.query,
                    documents=documents,
                    top_k=self.settings.memory.rerank_top_k  # 5
                )
                
                # 根据重排序分数更新SearchResult
                reranked_results = []
                for i, score in enumerate(rerank_response.scores):
                    if i < len(results):
                        result = results[i]
                        result.rerank_score = score
                        result.relevance_score = score  # 使用rerank分数作为最终相关性分数
                        result.metadata = result.metadata or {}
                        result.metadata.update({
                            'rerank_model': rerank_response.model,
                            'rerank_provider': rerank_response.provider,
                            'original_rank': i
                        })
                        reranked_results.append(result)
                
                # 按rerank分数降序排列
                reranked_results.sort(key=lambda x: x.rerank_score or 0, reverse=True)
                
                logger.info(
                    "Qwen3 rerank completed",
                    model=rerank_response.model,
                    original_count=len(results),
                    reranked_count=len(reranked_results),
                    cost=rerank_response.cost_usd
                )
                
                return reranked_results[:self.settings.memory.rerank_top_k]
                
            finally:
                await self.model_manager.close()
                
        except Exception as e:
            logger.warning(
                "Qwen3 rerank failed, falling back to rule-based rerank",
                error=str(e)
            )
            
            # 降级到基于规则的重排序
            fallback_func = self.rerank_algorithms.get(
                'relevance_time', 
                self._rerank_by_relevance_time
            )
            
            fallback_results = await fallback_func(results, query)
            return fallback_results[:self.settings.memory.rerank_top_k]

    async def _rerank_by_relevance_time(
        self, results: List[SearchResult], query: SearchQuery
    ) -> List[SearchResult]:
        """
        基于相关性和时间的重排序
        
        Args:
            results: 搜索结果
            query: 搜索查询
            
        Returns:
            List[SearchResult]: 重排序后的结果
        """
        current_time = datetime.utcnow()
        
        for result in results:
            # 基础相关性分数
            base_score = result.relevance_score
            
            # 时间衰减因子
            time_diff = current_time - result.memory_unit.created_at
            days_old = time_diff.days
            time_decay = max(0.1, 1.0 - (days_old / 30.0))  # 30天衰减期
            
            # 重要性加权
            importance_score = result.memory_unit.metadata.get('importance_score', 0.5)
            
            # 计算最终分数
            final_score = base_score * 0.6 + time_decay * 0.3 + importance_score * 0.1
            result.relevance_score = min(1.0, final_score)
        
        # 按最终分数排序
        return sorted(results, key=lambda x: x.relevance_score, reverse=True)

    async def _rerank_by_quality_boost(
        self, results: List[SearchResult], query: SearchQuery
    ) -> List[SearchResult]:
        """
        基于质量评分的重排序
        
        Args:
            results: 搜索结果
            query: 搜索查询
            
        Returns:
            List[SearchResult]: 重排序后的结果
        """
        for result in results:
            base_score = result.relevance_score
            quality_score = result.memory_unit.metadata.get('quality_score', 0.5)
            
            # 质量加权
            final_score = base_score * 0.7 + quality_score * 0.3
            result.relevance_score = min(1.0, final_score)
        
        return sorted(results, key=lambda x: x.relevance_score, reverse=True)

    async def _rerank_by_type_priority(
        self, results: List[SearchResult], query: SearchQuery
    ) -> List[SearchResult]:
        """
        基于记忆类型优先级的重排序
        
        Args:
            results: 搜索结果
            query: 搜索查询
            
        Returns:
            List[SearchResult]: 重排序后的结果
        """
        # 类型优先级权重
        type_weights = {
            MemoryUnitType.DOCUMENTATION: 1.0,
            MemoryUnitType.CONVERSATION: 0.8,
            MemoryUnitType.ARCHIVE: 0.6,
        }
        
        for result in results:
            base_score = result.relevance_score
            type_weight = type_weights.get(result.memory_unit.unit_type, 0.5)
            
            # 类型加权
            final_score = base_score * type_weight
            result.relevance_score = min(1.0, final_score)
        
        return sorted(results, key=lambda x: x.relevance_score, reverse=True)

    async def _generate_embedding(self, text: str) -> np.ndarray:
        """
        生成文本嵌入向量 (v1.4: 使用Qwen3-Embedding-8B)
        
        Args:
            text: 输入文本
            
        Returns:
            np.ndarray: 嵌入向量 (4096维)
        """
        # 检查缓存
        text_hash = str(hash(text))
        if text_hash in self.embedding_cache:
            return self.embedding_cache[text_hash]
        
        # 清理和预处理文本
        clean_text = await self.text_processor.clean_and_normalize(text)
        
        try:
            # v1.4: 使用Qwen3-Embedding-8B生成真实的4096维嵌入
            embedding_response = await self.model_manager.generate_embedding(
                model=self.settings.models.default_embedding_model,  # qwen3-embedding-8b
                text=clean_text
            )
            
            embedding_vector = np.array(embedding_response.embedding, dtype=np.float32)
            
            # 验证向量维度
            expected_dim = self.settings.qdrant.vector_size  # 4096
            if len(embedding_vector) != expected_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {expected_dim}, got {len(embedding_vector)}"
                )
            
            logger.debug(
                "Qwen3 embedding generated",
                text_length=len(clean_text),
                model=embedding_response.model,
                dimension=embedding_response.dimension,
                cost=embedding_response.cost_usd
            )
            
            # 缓存结果
            await self._cache_embedding(text_hash, embedding_vector)
            
            return embedding_vector
                
        except Exception as e:
            logger.error(
                "Qwen3 embedding generation failed",
                text_length=len(clean_text),
                error=str(e)
            )
            
            # 降级到随机向量（仅用于开发测试）
            logger.warning("Falling back to random embedding vector")
            vector_size = self.settings.qdrant.vector_size
            embedding_vector = np.random.random(vector_size).astype(np.float32)
            
            # 缓存降级结果
            await self._cache_embedding(text_hash, embedding_vector)
            
            return embedding_vector

    def _build_qdrant_filter(self, request: RetrievalRequest) -> Optional[qdrant_models.Filter]:
        """
        构建Qdrant过滤条件
        
        Args:
            request: 检索请求
            
        Returns:
            Optional[qdrant_models.Filter]: 过滤条件
        """
        conditions = []
        
        # 项目ID过滤 - 已删除：全局共享记忆
        # if request.project_id:
        #     conditions.append(
        #         qdrant_models.FieldCondition(
        #             key="project_id",
        #             match=qdrant_models.MatchValue(value=request.project_id)
        #         )
        #     )
        
        # 记忆单元类型过滤
        if request.unit_types:
            type_conditions = [
                qdrant_models.FieldCondition(
                    key="unit_type",
                    match=qdrant_models.MatchValue(value=unit_type.value)
                )
                for unit_type in request.unit_types
            ]
            if len(type_conditions) == 1:
                conditions.append(type_conditions[0])
            else:
                conditions.append(
                    qdrant_models.Filter(should=type_conditions)
                )
        
        # 过期时间过滤
        if not request.include_expired:
            # 使用时间戳而不是ISO字符串
            current_timestamp = datetime.utcnow().timestamp()
            conditions.append(
                qdrant_models.Filter(
                    should=[
                        qdrant_models.IsNullCondition(
                            is_null=qdrant_models.PayloadField(key="expires_at")
                        ),
                        qdrant_models.FieldCondition(
                            key="expires_at",
                            range=qdrant_models.Range(gte=current_timestamp)
                        )
                    ]
                )
            )
        
        if not conditions:
            return None
        
        return qdrant_models.Filter(must=conditions) if len(conditions) > 1 else conditions[0]

    def _select_retrieval_strategy(self, request: RetrievalRequest) -> str:
        """
        选择检索策略
        
        Args:
            request: 检索请求
            
        Returns:
            str: 策略名称
        """
        if request.hybrid_search:
            return 'hybrid'
        elif request.query.query_type == 'semantic':
            return 'semantic_only'
        else:
            return 'keyword_only'

    async def _get_memory_unit_by_id(self, memory_id: str) -> Optional[MemoryUnitModel]:
        """
        根据ID获取记忆单元
        
        Args:
            memory_id: 记忆单元ID
            
        Returns:
            Optional[MemoryUnitModel]: 记忆单元
        """
        try:
            async with get_db_session() as session:
                from sqlalchemy import select
                from claude_memory.models.data_models import MemoryUnitDB
                result = await session.execute(
                    select(MemoryUnitDB).filter(
                        MemoryUnitDB.id == uuid.UUID(memory_id)
                    )
                )
                memory_unit_db = result.scalar_one_or_none()
                if memory_unit_db:
                    # 转换为 Pydantic 模型
                    return MemoryUnitModel(
                        id=str(memory_unit_db.id),
                        project_id=memory_unit_db.project_id,
                        conversation_id=str(memory_unit_db.conversation_id),
                        unit_type=memory_unit_db.unit_type,
                        title=memory_unit_db.title,
                        summary=memory_unit_db.summary,
                        content=memory_unit_db.content,
                        keywords=memory_unit_db.keywords or [],
                        relevance_score=memory_unit_db.relevance_score,
                        token_count=memory_unit_db.token_count,
                        created_at=memory_unit_db.created_at,
                        updated_at=memory_unit_db.updated_at,
                        expires_at=memory_unit_db.expires_at,
                        metadata=memory_unit_db.meta_data or {},
                        is_active=memory_unit_db.is_active
                    )
                return None
        except Exception as e:
            logger.warning(
                "Failed to get memory unit by ID",
                memory_id=memory_id,
                error=str(e)
            )
            return None

    async def _get_collections(self):
        """获取Qdrant集合列表"""
        return await self.qdrant_client.get_collections()

    def _generate_search_cache_key(self, request: RetrievalRequest) -> str:
        """
        生成搜索缓存键
        
        Args:
            request: 检索请求
            
        Returns:
            str: 缓存键
        """
        import hashlib
        
        key_data = (
            request.query.query +
            str(request.limit) +
            str(request.min_score) +
            str(request.include_expired) +
            str(request.unit_types) +
            str(request.rerank) +
            str(request.hybrid_search)
        )
        
        return f"search_{hashlib.md5(key_data.encode()).hexdigest()}"

    async def _cache_embedding(self, text_hash: str, embedding: np.ndarray) -> None:
        """
        缓存嵌入向量
        
        Args:
            text_hash: 文本哈希
            embedding: 嵌入向量
        """
        # 控制缓存大小
        if len(self.embedding_cache) >= self.max_cache_size:
            # 删除最旧的一半缓存
            old_keys = list(self.embedding_cache.keys())[:self.max_cache_size // 2]
            for key in old_keys:
                del self.embedding_cache[key]
        
        self.embedding_cache[text_hash] = embedding

    async def _cache_search_result(self, cache_key: str, result: RetrievalResult) -> None:
        """
        缓存搜索结果
        
        Args:
            cache_key: 缓存键
            result: 搜索结果
        """
        # 控制缓存大小
        if len(self.search_cache) >= self.max_cache_size:
            # 删除最旧的一半缓存
            old_keys = list(self.search_cache.keys())[:self.max_cache_size // 2]
            for key in old_keys:
                del self.search_cache[key]
        
        self.search_cache[cache_key] = result

    @handle_exceptions(logger=logger, default_return=0)
    async def count_memories(
        self, 
        unit_types: Optional[List[MemoryUnitType]] = None,
        include_expired: bool = False
    ) -> int:
        """
        统计记忆单元数量
        
        Args:
            unit_types: 记忆单元类型过滤
            include_expired: 是否包含过期记忆
            
        Returns:
            int: 记忆单元数量
        """
        async with get_db_session() as session:
            from sqlalchemy import select
            from claude_memory.models.data_models import MemoryUnitDB
            query = select(func.count(MemoryUnitDB.id))
            
            # 应用类型过滤
            if unit_types:
                query = query.filter(MemoryUnitDB.unit_type.in_(unit_types))
            
            # 排除过期记忆
            if not include_expired:
                query = query.filter(
                    or_(
                        MemoryUnitDB.expires_at.is_(None),
                        MemoryUnitDB.expires_at > datetime.utcnow()
                    )
                )
            
            result = await session.execute(query)
            count = result.scalar()
            return count or 0

    @handle_exceptions(logger=logger, default_return=False)
    async def delete_memory_unit(self, memory_id: uuid.UUID) -> bool:
        """
        删除记忆单元
        
        Args:
            memory_id: 记忆单元ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 从Qdrant删除
            await self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=qdrant_models.PointIdsList(
                    points=[str(memory_id)]
                )
            )
            
            # 从数据库删除
            from sqlalchemy import delete
            
            async with get_db_session() as session:
                from claude_memory.models.data_models import MemoryUnitDB
                await session.execute(
                    delete(MemoryUnitDB).where(
                        MemoryUnitDB.id == memory_id
                    )
                )
                
                await session.execute(
                    delete(EmbeddingDB).where(
                        EmbeddingDB.memory_unit_id == memory_id
                )
            )
            
            await session.commit()
            
            logger.info("Memory unit deleted", memory_id=str(memory_id))
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete memory unit",
                memory_id=str(memory_id),
                error=str(e)
            )
            # rollback is handled by the context manager
            return False
    
    async def close(self) -> None:
        """关闭资源"""
        try:
            if hasattr(self, 'model_manager') and self.model_manager:
                await self.model_manager.close()
                logger.info("SemanticRetriever model_manager closed")
            
            if hasattr(self, 'qdrant_client') and self.qdrant_client:
                await self.qdrant_client.close()
                logger.info("SemanticRetriever qdrant_client closed")
        except Exception as e:
            logger.warning(f"Error closing SemanticRetriever resources: {e}")

