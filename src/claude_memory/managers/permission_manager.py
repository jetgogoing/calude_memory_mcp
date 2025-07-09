"""
Claude记忆管理MCP服务 - 权限管理器

管理项目级别的访问权限和安全控制。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional, Set
from enum import Enum

import structlog
from pydantic import BaseModel, Field

from claude_memory.config.settings import get_settings
from claude_memory.utils.error_handling import handle_exceptions, SecurityError

logger = structlog.get_logger(__name__)


class PermissionLevel(str, Enum):
    """权限级别枚举"""
    
    NONE = "none"           # 无权限
    READ = "read"           # 只读权限
    WRITE = "write"         # 读写权限
    ADMIN = "admin"         # 管理员权限
    OWNER = "owner"         # 所有者权限


class ProjectPermission(BaseModel):
    """项目权限模型"""
    
    user_id: str = Field(description="用户ID")
    project_id: str = Field(description="项目ID")
    permission_level: PermissionLevel = Field(description="权限级别")
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="授权时间")
    granted_by: Optional[str] = Field(default=None, description="授权者ID")
    expires_at: Optional[datetime] = Field(default=None, description="过期时间")
    
    class Config:
        from_attributes = True


class PermissionRequest(BaseModel):
    """权限请求模型"""
    
    user_id: str = Field(description="请求用户ID")
    project_ids: List[str] = Field(description="请求访问的项目ID列表")
    required_permission: PermissionLevel = Field(description="所需权限级别")
    action: str = Field(description="请求执行的操作")
    
    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    """权限响应模型"""
    
    allowed: bool = Field(description="是否允许")
    project_permissions: Dict[str, PermissionLevel] = Field(description="各项目的权限级别")
    denied_projects: List[str] = Field(default_factory=list, description="被拒绝的项目列表")
    reason: Optional[str] = Field(default=None, description="拒绝原因")
    
    class Config:
        from_attributes = True


class PermissionManager:
    """
    权限管理器
    
    功能特性：
    - 项目级别的权限控制
    - 基于角色的访问控制 (RBAC)
    - 权限继承和级联
    - 临时权限支持
    - 审计日志
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # 权限缓存（生产环境应使用Redis）
        self._permission_cache: Dict[str, Dict[str, PermissionLevel]] = {}
        
        # 权限级别层次
        self.permission_hierarchy = {
            PermissionLevel.NONE: 0,
            PermissionLevel.READ: 1,
            PermissionLevel.WRITE: 2,
            PermissionLevel.ADMIN: 3,
            PermissionLevel.OWNER: 4
        }
        
        # 操作所需的最低权限
        self.action_permissions = {
            "search": PermissionLevel.READ,
            "read": PermissionLevel.READ,
            "create": PermissionLevel.WRITE,
            "update": PermissionLevel.WRITE,
            "delete": PermissionLevel.ADMIN,
            "manage_permissions": PermissionLevel.ADMIN,
            "transfer_ownership": PermissionLevel.OWNER
        }
        
        logger.info("PermissionManager initialized")
    
    @handle_exceptions(logger=logger, reraise=True)
    async def check_permissions(self, request: PermissionRequest) -> PermissionResponse:
        """
        检查用户对项目的权限
        
        Args:
            request: 权限请求
            
        Returns:
            PermissionResponse: 权限检查结果
        """
        # 系统用户不受隔离模式限制
        is_system_user = (request.user_id == "system" or 
                         request.user_id == os.environ.get("SYSTEM_USER_ID"))
        
        # 如果是严格隔离模式且未启用跨项目搜索，直接拒绝（系统用户除外）
        if (not is_system_user and
            self.settings.project.project_isolation_mode == "strict" and 
            not self.settings.project.enable_cross_project_search and
            len(request.project_ids) > 1):
            return PermissionResponse(
                allowed=False,
                project_permissions={},
                denied_projects=request.project_ids,
                reason="Cross-project access is disabled in strict isolation mode"
            )
        
        # 获取用户的项目权限
        user_permissions = await self._get_user_permissions(request.user_id)
        
        # 检查每个项目的权限
        project_permissions = {}
        denied_projects = []
        
        for project_id in request.project_ids:
            # 系统用户对所有项目都有OWNER权限
            if is_system_user:
                user_permission = PermissionLevel.OWNER
            else:
                user_permission = user_permissions.get(project_id, PermissionLevel.NONE)
            
            project_permissions[project_id] = user_permission
            
            # 检查权限是否足够
            if not self._has_sufficient_permission(
                user_permission, 
                request.required_permission
            ):
                denied_projects.append(project_id)
        
        # 判断整体是否允许
        allowed = len(denied_projects) == 0
        
        # 记录审计日志
        await self._log_permission_check(request, allowed, denied_projects)
        
        return PermissionResponse(
            allowed=allowed,
            project_permissions=project_permissions,
            denied_projects=denied_projects,
            reason=None if allowed else f"Insufficient permissions for projects: {denied_projects}"
        )
    
    @handle_exceptions(logger=logger, reraise=True)
    async def grant_permission(
        self,
        user_id: str,
        project_id: str,
        permission_level: PermissionLevel,
        granted_by: str,
        expires_at: Optional[datetime] = None
    ) -> ProjectPermission:
        """
        授予用户项目权限
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            permission_level: 权限级别
            granted_by: 授权者ID
            expires_at: 过期时间（可选）
            
        Returns:
            ProjectPermission: 授权记录
        """
        # 验证授权者权限
        grantor_permission = await self._get_user_project_permission(granted_by, project_id)
        if not self._can_grant_permission(grantor_permission, permission_level):
            raise SecurityError(
                f"User {granted_by} cannot grant {permission_level} permission"
            )
        
        # 创建权限记录
        permission = ProjectPermission(
            user_id=user_id,
            project_id=project_id,
            permission_level=permission_level,
            granted_by=granted_by,
            expires_at=expires_at
        )
        
        # 存储权限（实际应存储到数据库）
        await self._store_permission(permission)
        
        # 更新缓存
        self._update_permission_cache(user_id, project_id, permission_level)
        
        logger.info(
            "Permission granted",
            user_id=user_id,
            project_id=project_id,
            permission_level=permission_level,
            granted_by=granted_by
        )
        
        return permission
    
    @handle_exceptions(logger=logger, reraise=True)
    async def revoke_permission(
        self,
        user_id: str,
        project_id: str,
        revoked_by: str
    ) -> bool:
        """
        撤销用户项目权限
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            revoked_by: 撤销者ID
            
        Returns:
            bool: 是否成功撤销
        """
        # 验证撤销者权限
        revoker_permission = await self._get_user_project_permission(revoked_by, project_id)
        if self.permission_hierarchy.get(revoker_permission, 0) < self.permission_hierarchy[PermissionLevel.ADMIN]:
            raise SecurityError(
                f"User {revoked_by} cannot revoke permissions"
            )
        
        # 不能撤销所有者权限
        current_permission = await self._get_user_project_permission(user_id, project_id)
        if current_permission == PermissionLevel.OWNER and revoked_by != user_id:
            raise SecurityError("Cannot revoke owner permission")
        
        # 删除权限记录（实际应从数据库删除）
        await self._delete_permission(user_id, project_id)
        
        # 更新缓存
        self._update_permission_cache(user_id, project_id, PermissionLevel.NONE)
        
        logger.info(
            "Permission revoked",
            user_id=user_id,
            project_id=project_id,
            revoked_by=revoked_by
        )
        
        return True
    
    def _has_sufficient_permission(
        self,
        user_permission: PermissionLevel,
        required_permission: PermissionLevel
    ) -> bool:
        """
        检查用户权限是否足够
        
        Args:
            user_permission: 用户当前权限
            required_permission: 所需权限
            
        Returns:
            bool: 权限是否足够
        """
        user_level = self.permission_hierarchy.get(user_permission, 0)
        required_level = self.permission_hierarchy.get(required_permission, 0)
        
        return user_level >= required_level
    
    def _can_grant_permission(
        self,
        grantor_permission: PermissionLevel,
        permission_to_grant: PermissionLevel
    ) -> bool:
        """
        检查是否可以授予权限
        
        Args:
            grantor_permission: 授权者权限
            permission_to_grant: 要授予的权限
            
        Returns:
            bool: 是否可以授权
        """
        # 只能授予低于或等于自己权限级别的权限
        grantor_level = self.permission_hierarchy.get(grantor_permission, 0)
        grant_level = self.permission_hierarchy.get(permission_to_grant, 0)
        
        # 至少需要管理员权限才能授权
        return (grantor_level >= self.permission_hierarchy[PermissionLevel.ADMIN] and
                grant_level <= grantor_level)
    
    async def _get_user_permissions(self, user_id: str) -> Dict[str, PermissionLevel]:
        """
        获取用户的所有项目权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict[str, PermissionLevel]: 项目ID到权限级别的映射
        """
        # 检查缓存
        if user_id in self._permission_cache:
            return self._permission_cache[user_id]
        
        # 实际应从数据库加载
        # 这里暂时返回模拟数据
        permissions = {}
        
        # 如果是系统用户，给予所有权限
        if user_id == "system" or user_id == os.environ.get("SYSTEM_USER_ID"):
            # 系统用户对所有项目都有所有者权限
            return {}
        else:
            # 默认用户对默认项目有读写权限
            permissions["default"] = PermissionLevel.WRITE
        
        # 更新缓存
        self._permission_cache[user_id] = permissions
        
        return permissions
    
    async def _get_user_project_permission(
        self,
        user_id: str,
        project_id: str
    ) -> PermissionLevel:
        """
        获取用户对特定项目的权限
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            
        Returns:
            PermissionLevel: 权限级别
        """
        # 系统用户对所有项目都有所有者权限
        if user_id == "system" or user_id == os.environ.get("SYSTEM_USER_ID"):
            return PermissionLevel.OWNER
            
        permissions = await self._get_user_permissions(user_id)
        return permissions.get(project_id, PermissionLevel.NONE)
    
    def _update_permission_cache(
        self,
        user_id: str,
        project_id: str,
        permission_level: PermissionLevel
    ):
        """更新权限缓存"""
        if user_id not in self._permission_cache:
            self._permission_cache[user_id] = {}
        
        if permission_level == PermissionLevel.NONE:
            self._permission_cache[user_id].pop(project_id, None)
        else:
            self._permission_cache[user_id][project_id] = permission_level
    
    async def _store_permission(self, permission: ProjectPermission):
        """存储权限记录（实际应存储到数据库）"""
        # TODO: 实现数据库存储
        pass
    
    async def _delete_permission(self, user_id: str, project_id: str):
        """删除权限记录（实际应从数据库删除）"""
        # TODO: 实现数据库删除
        pass
    
    async def _log_permission_check(
        self,
        request: PermissionRequest,
        allowed: bool,
        denied_projects: List[str]
    ):
        """记录权限检查日志"""
        logger.info(
            "Permission check",
            user_id=request.user_id,
            action=request.action,
            projects=request.project_ids,
            allowed=allowed,
            denied_projects=denied_projects
        )


# 全局权限管理器实例
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """获取全局权限管理器实例"""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager