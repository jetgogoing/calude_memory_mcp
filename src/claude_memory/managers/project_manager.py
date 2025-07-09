"""
Claude记忆管理MCP服务 - 项目管理器

管理跨项目记忆共享的项目配置和操作。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database.sync_session import get_sync_session
from ..models.data_models import ProjectDB, ProjectModel
import structlog

logger = structlog.get_logger(__name__)


class ProjectManager:
    """项目管理器"""
    
    def __init__(self):
        """初始化项目管理器"""
        self.default_project_id = os.environ.get("DEFAULT_PROJECT_ID", "default")
        self._ensure_default_project()
    
    def _ensure_default_project(self) -> None:
        """确保默认项目存在"""
        try:
            with get_sync_session() as session:
                default_project = session.query(ProjectDB).filter_by(id=self.default_project_id).first()
                if not default_project:
                    default_project = ProjectDB(
                        id=self.default_project_id,
                        name="默认项目",
                        description="系统默认项目，用于未指定项目的记忆",
                        settings={},
                        is_active=True
                    )
                    session.add(default_project)
                    session.commit()
        except Exception as e:
            logger.error(f"创建默认项目失败: {e}")
    
    def create_project(
        self,
        project_id: str,
        name: str,
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> ProjectModel:
        """创建新项目"""
        try:
            with get_sync_session() as session:
                # 检查项目是否已存在
                existing = session.query(ProjectDB).filter_by(id=project_id).first()
                if existing:
                    raise ValueError(f"项目ID '{project_id}' 已存在")
                
                # 创建新项目
                project_db = ProjectDB(
                    id=project_id,
                    name=name,
                    description=description,
                    settings=settings or {},
                    is_active=True
                )
                session.add(project_db)
                session.commit()
                session.refresh(project_db)
                
                return ProjectModel.model_validate(project_db)
                
        except IntegrityError:
            raise ValueError(f"项目ID '{project_id}' 已存在")
        except Exception as e:
            logger.error(f"创建项目失败: {e}")
            raise
    
    def get_project(self, project_id: str) -> Optional[ProjectModel]:
        """获取项目信息"""
        try:
            with get_sync_session() as session:
                project_db = session.query(ProjectDB).filter_by(id=project_id).first()
                if project_db:
                    return ProjectModel.model_validate(project_db)
                return None
        except Exception as e:
            logger.error(f"获取项目失败: {e}")
            return None
    
    def list_projects(self, only_active: bool = True) -> List[ProjectModel]:
        """列出所有项目"""
        try:
            with get_sync_session() as session:
                query = session.query(ProjectDB)
                if only_active:
                    query = query.filter_by(is_active=True)
                
                projects = query.order_by(ProjectDB.created_at.desc()).all()
                return [ProjectModel.model_validate(p) for p in projects]
        except Exception as e:
            logger.error(f"列出项目失败: {e}")
            return []
    
    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> Optional[ProjectModel]:
        """更新项目信息"""
        try:
            with get_sync_session() as session:
                project_db = session.query(ProjectDB).filter_by(id=project_id).first()
                if not project_db:
                    return None
                
                if name is not None:
                    project_db.name = name
                if description is not None:
                    project_db.description = description
                if settings is not None:
                    project_db.settings = settings
                if is_active is not None:
                    project_db.is_active = is_active
                
                project_db.updated_at = datetime.utcnow()
                session.commit()
                session.refresh(project_db)
                
                return ProjectModel.model_validate(project_db)
        except Exception as e:
            logger.error(f"更新项目失败: {e}")
            return None
    
    def delete_project(self, project_id: str, soft_delete: bool = True) -> bool:
        """删除项目
        
        Args:
            project_id: 项目ID
            soft_delete: 是否软删除（仅标记为inactive）
        
        Returns:
            是否删除成功
        """
        if project_id == self.default_project_id:
            logger.error("不能删除默认项目")
            return False
        
        try:
            with get_sync_session() as session:
                project_db = session.query(ProjectDB).filter_by(id=project_id).first()
                if not project_db:
                    return False
                
                if soft_delete:
                    # 软删除：仅标记为inactive
                    project_db.is_active = False
                    project_db.updated_at = datetime.utcnow()
                    session.commit()
                else:
                    # 硬删除：实际删除记录（注意：这会级联删除所有相关数据）
                    session.delete(project_db)
                    session.commit()
                
                return True
        except Exception as e:
            logger.error(f"删除项目失败: {e}")
            return False
    
    def get_project_statistics(self, project_id: str) -> Dict[str, Any]:
        """获取项目统计信息"""
        try:
            with get_sync_session() as session:
                # 使用原生SQL查询统计信息
                result = session.execute(
                    text("""
                    SELECT 
                        COUNT(DISTINCT c.id) as conversation_count,
                        COUNT(DISTINCT mu.id) as memory_unit_count,
                        COALESCE(SUM(c.token_count), 0) as total_tokens,
                        MAX(c.started_at) as last_activity
                    FROM projects p
                    LEFT JOIN conversations c ON p.id = c.project_id
                    LEFT JOIN memory_units mu ON p.id = mu.project_id
                    WHERE p.id = :project_id AND p.is_active = true
                    GROUP BY p.id
                    """),
                    {"project_id": project_id}
                ).first()
                
                if result:
                    return {
                        "project_id": project_id,
                        "conversation_count": result.conversation_count,
                        "memory_unit_count": result.memory_unit_count,
                        "total_tokens": result.total_tokens,
                        "last_activity": result.last_activity
                    }
                else:
                    return {
                        "project_id": project_id,
                        "conversation_count": 0,
                        "memory_unit_count": 0,
                        "total_tokens": 0,
                        "last_activity": None
                    }
        except Exception as e:
            logger.error(f"获取项目统计失败: {e}")
            return {}
    
    def validate_project_id(self, project_id: str) -> bool:
        """验证项目ID是否有效"""
        if not project_id:
            return False
        
        # 检查项目是否存在且激活
        project = self.get_project(project_id)
        return project is not None and project.is_active
    
    def get_or_create_project(self, project_id: str, name: Optional[str] = None) -> ProjectModel:
        """获取或创建项目"""
        project = self.get_project(project_id)
        if project:
            return project
        
        # 创建新项目
        return self.create_project(
            project_id=project_id,
            name=name or f"项目 {project_id}",
            description=f"自动创建的项目 - {datetime.utcnow().isoformat()}"
        )


# 全局项目管理器实例
_project_manager: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    """获取全局项目管理器实例"""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager