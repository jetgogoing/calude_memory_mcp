"""
Claude记忆管理MCP服务 - 同步数据库会话管理

为不需要异步的组件提供同步数据库访问。
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from claude_memory.config.settings import get_settings


class SyncSessionManager:
    """同步会话管理器"""
    
    _instance = None
    _engine = None
    _session_factory = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._engine is None:
            settings = get_settings()
            # 转换异步URL为同步URL
            sync_url = settings.database.database_url
            if sync_url.startswith("postgresql+asyncpg://"):
                sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")
            
            self._engine = create_engine(
                sync_url,
                poolclass=StaticPool,
                echo=False
            )
            self._session_factory = sessionmaker(bind=self._engine)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """获取同步数据库会话"""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# 全局同步会话管理器
_sync_manager = SyncSessionManager()


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """获取同步数据库会话的便捷函数"""
    with _sync_manager.get_session() as session:
        yield session


def get_sync_db_session() -> Generator[Session, None, None]:
    """获取同步数据库会话 - 用于测试和其他同步代码"""
    session = _sync_manager._session_factory()
    try:
        yield session
    finally:
        session.close()