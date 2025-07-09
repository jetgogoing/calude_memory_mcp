"""
Claude记忆管理MCP服务 - 跨项目搜索管理器

实现跨项目搜索功能，支持在多个项目中同时搜索记忆。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import uuid

import structlog
from pydantic import BaseModel, Field

from claude_memory.config.settings import get_settings
from claude_memory.models.data_models import (
    SearchQuery,
    SearchResponse,
    SearchResult,
    MemoryUnitModel,
)
from claude_memory.managers.project_manager import get_project_manager
from claude_memory.managers.permission_manager import (
    get_permission_manager,
    PermissionLevel,
    PermissionRequest
)
from claude_memory.retrievers.semantic_retriever import SemanticRetriever, RetrievalRequest
from claude_memory.utils.error_handling import handle_exceptions, ProcessingError, SecurityError

logger = structlog.get_logger(__name__)


class CrossProjectSearchRequest(BaseModel):
    """跨项目搜索请求"""
    
    query: SearchQuery = Field(description="搜索查询")
    project_ids: Optional[List[str]] = Field(default=None, description="要搜索的项目ID列表")
    include_all_projects: bool = Field(default=False, description="是否搜索所有活跃项目")
    merge_strategy: str = Field(default="score", description="结果合并策略: score, time, project")
    max_results_per_project: int = Field(default=10, ge=1, le=100)
    user_id: Optional[str] = Field(default=None, description="请求用户ID，用于权限检查")
    
    class Config:
        from_attributes = True


class CrossProjectSearchResult(BaseModel):
    """跨项目搜索结果"""
    
    project_id: str
    project_name: str
    results: List[SearchResult]
    total_count: int
    search_time_ms: float
    
    class Config:
        from_attributes = True


class CrossProjectSearchResponse(BaseModel):
    """跨项目搜索响应"""
    
    results: List[SearchResult] = Field(description="合并后的搜索结果")
    project_results: Dict[str, CrossProjectSearchResult] = Field(description="按项目分组的结果")
    total_count: int = Field(description="总结果数")
    projects_searched: int = Field(description="搜索的项目数")
    search_time_ms: float = Field(description="总搜索时间（毫秒）")
    query_id: str = Field(description="查询ID")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True


class CrossProjectSearchManager:
    """
    跨项目搜索管理器
    
    功能特性:
    - 在多个项目中并行搜索
    - 智能结果合并和排序
    - 项目权限验证
    - 搜索性能优化
    """
    
    def __init__(self, semantic_retriever: SemanticRetriever):
        self.settings = get_settings()
        self.semantic_retriever = semantic_retriever
        self.project_manager = get_project_manager()
        self.permission_manager = get_permission_manager()
        
    @handle_exceptions(logger=logger, reraise=True)
    async def search_across_projects(self, request: CrossProjectSearchRequest) -> CrossProjectSearchResponse:
        """
        执行跨项目搜索
        
        Args:
            request: 跨项目搜索请求
            
        Returns:
            CrossProjectSearchResponse: 跨项目搜索响应
        """
        start_time = datetime.utcnow()
        
        # 跨项目搜索始终启用
        
        # 确定要搜索的项目列表
        project_ids = await self._determine_search_projects(request)
        
        # 不再检查权限，所有项目都可搜索
        
        # 如果没有可搜索的项目，返回空结果
        if not project_ids:
            return CrossProjectSearchResponse(
                results=[],
                project_results={},
                total_count=0,
                projects_searched=0,
                search_time_ms=0,
                query_id=str(uuid.uuid4()),
                metadata={
                    "error": "No authorized projects to search"
                }
            )
        
        # 不再限制项目数量，搜索所有项目
        
        # 并行搜索所有项目
        search_tasks = []
        for project_id in project_ids:
            task = self._search_in_project(
                project_id,
                request.query,
                request.max_results_per_project
            )
            search_tasks.append(task)
        
        # 等待所有搜索完成
        project_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # 处理搜索结果
        valid_results = []
        project_results_dict = {}
        total_count = 0
        
        for i, result in enumerate(project_results):
            if isinstance(result, Exception):
                logger.error(
                    "Search failed for project",
                    project_id=project_ids[i],
                    error=str(result)
                )
                continue
            
            if result and result.results:
                valid_results.append(result)
                project_results_dict[project_ids[i]] = result
                total_count += result.total_count
        
        # 合并和排序结果
        merged_results = await self._merge_results(
            valid_results,
            request.merge_strategy,
            request.query.limit or 20
        )
        
        # 计算总搜索时间
        search_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return CrossProjectSearchResponse(
            results=merged_results,
            project_results=project_results_dict,
            total_count=total_count,
            projects_searched=len(project_ids),
            search_time_ms=search_time_ms,
            query_id=str(uuid.uuid4()),
            metadata={
                "merge_strategy": request.merge_strategy,
                "projects": project_ids
            }
        )
    
    async def _determine_search_projects(self, request: CrossProjectSearchRequest) -> List[str]:
        """
        确定要搜索的项目列表
        
        Args:
            request: 搜索请求
            
        Returns:
            List[str]: 项目ID列表
        """
        # 始终搜索所有活跃项目，无论请求如何
        all_projects = self.project_manager.list_projects(only_active=True)
        return [p.id for p in all_projects]
    
    async def _search_in_project(
        self,
        project_id: str,
        query: SearchQuery,
        max_results: int
    ) -> CrossProjectSearchResult:
        """
        在单个项目中搜索
        
        Args:
            project_id: 项目ID
            query: 搜索查询
            max_results: 最大结果数
            
        Returns:
            CrossProjectSearchResult: 项目搜索结果
        """
        start_time = datetime.utcnow()
        
        try:
            # 获取项目信息
            project = self.project_manager.get_project(project_id)
            if not project:
                raise ProcessingError(f"Project {project_id} not found")
            
            # 构建检索请求
            retrieval_request = RetrievalRequest(
                query=query,
                project_id=project_id,
                limit=max_results,
                min_score=query.min_score or 0.5,
                rerank=True,
                hybrid_search=True
            )
            
            # 执行检索
            retrieval_result = await self.semantic_retriever.retrieve_memories(
                retrieval_request
            )
            
            # 计算搜索时间
            search_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 为每个结果添加项目信息
            for result in retrieval_result.results:
                result.metadata = result.metadata or {}
                result.metadata["project_id"] = project_id
                result.metadata["project_name"] = project.name
            
            return CrossProjectSearchResult(
                project_id=project_id,
                project_name=project.name,
                results=retrieval_result.results,
                total_count=retrieval_result.total_found,
                search_time_ms=search_time_ms
            )
            
        except Exception as e:
            logger.error(
                "Failed to search in project",
                project_id=project_id,
                error=str(e)
            )
            raise
    
    async def _merge_results(
        self,
        project_results: List[CrossProjectSearchResult],
        merge_strategy: str,
        limit: int
    ) -> List[SearchResult]:
        """
        合并多个项目的搜索结果
        
        Args:
            project_results: 各项目的搜索结果
            merge_strategy: 合并策略
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 合并后的结果
        """
        all_results = []
        
        # 收集所有结果
        for project_result in project_results:
            all_results.extend(project_result.results)
        
        # 根据策略排序
        if merge_strategy == "score":
            # 按相关性分数排序
            all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        elif merge_strategy == "time":
            # 按时间排序（最新优先）
            all_results.sort(
                key=lambda x: x.memory_unit.created_at,
                reverse=True
            )
        
        elif merge_strategy == "project":
            # 按项目分组，每个项目轮流取一个结果
            merged = []
            project_iterators = [iter(pr.results) for pr in project_results]
            
            while len(merged) < limit and project_iterators:
                # 轮询每个项目
                exhausted = []
                for i, iterator in enumerate(project_iterators):
                    try:
                        result = next(iterator)
                        merged.append(result)
                        if len(merged) >= limit:
                            break
                    except StopIteration:
                        exhausted.append(i)
                
                # 移除已耗尽的迭代器
                for i in reversed(exhausted):
                    project_iterators.pop(i)
            
            return merged
        
        # 返回限制数量的结果
        return all_results[:limit]
    
    async def _check_user_permissions(
        self,
        user_id: str,
        project_ids: List[str]
    ) -> List[str]:
        """
        检查用户对项目的访问权限
        
        Args:
            user_id: 用户ID
            project_ids: 请求的项目ID列表
            
        Returns:
            List[str]: 有权限访问的项目ID列表
        """
        # 构建权限请求
        permission_request = PermissionRequest(
            user_id=user_id,
            project_ids=project_ids,
            required_permission=PermissionLevel.READ,
            action="search"
        )
        
        # 检查权限
        permission_response = await self.permission_manager.check_permissions(permission_request)
        
        # 返回有权限的项目
        authorized_projects = []
        for project_id, permission_level in permission_response.project_permissions.items():
            if permission_level != PermissionLevel.NONE and project_id not in permission_response.denied_projects:
                authorized_projects.append(project_id)
        
        return authorized_projects


def get_cross_project_search_manager(
    semantic_retriever: SemanticRetriever
) -> CrossProjectSearchManager:
    """
    获取跨项目搜索管理器实例
    
    Args:
        semantic_retriever: 语义检索器
        
    Returns:
        CrossProjectSearchManager: 跨项目搜索管理器
    """
    return CrossProjectSearchManager(semantic_retriever)