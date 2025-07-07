"""
Claude记忆管理MCP服务 - 数据库会话管理器

解决SQLAlchemy AsyncSession并发冲突问题，实现线程安全的会话管理。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from claude_memory.config.settings import get_settings

logger = structlog.get_logger(__name__)


class SessionManager:
    """
    数据库会话管理器
    
    解决SQLAlchemy AsyncSession并发问题：
    - 为每个操作创建独立的会话
    - 实现连接池管理
    - 提供上下文管理器接口
    - 确保会话正确关闭
    """
    
    _instance: Optional[SessionManager] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        if SessionManager._instance is not None:
            raise RuntimeError("SessionManager is a singleton. Use get_instance() instead.")
        
        self.settings = get_settings()
        self.engine = None
        self.session_factory = None
        self._initialized = False
        
    @classmethod
    async def get_instance(cls) -> SessionManager:
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance.initialize()
        return cls._instance
    
    async def initialize(self) -> None:
        """初始化数据库引擎和会话工厂"""
        if self._initialized:
            return
            
        try:
            # 配置数据库URL
            if self.settings.database.database_url.startswith("sqlite"):
                database_url = self.settings.database.database_url.replace("sqlite://", "sqlite+aiosqlite://")
                # SQLite特殊配置
                self.engine = create_async_engine(
                    database_url,
                    echo=self.settings.database.echo,
                    # SQLite使用StaticPool避免连接池问题
                    poolclass=StaticPool,
                    connect_args={
                        "check_same_thread": False,
                    },
                )
            else:
                # PostgreSQL异步连接
                database_url = self.settings.database.database_url.replace("postgresql://", "postgresql+asyncpg://")
                self.engine = create_async_engine(
                    database_url,
                    echo=self.settings.database.echo,
                    pool_size=self.settings.database.pool_size,
                    max_overflow=self.settings.database.max_overflow,
                    pool_timeout=self.settings.database.pool_timeout,
                )
            
            # 创建会话工厂
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False,
            )
            
            self._initialized = True
            logger.info("SessionManager initialized successfully", database_url=database_url)
            
        except Exception as e:
            logger.error("Failed to initialize SessionManager", error=str(e))
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取数据库会话的上下文管理器
        
        使用方式:
        async with session_manager.get_session() as session:
            result = await session.execute(query)
            await session.commit()
        """
        if not self._initialized:
            await self.initialize()
            
        session = self.session_factory()
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Session operation failed, rolling back", error=str(e))
            raise
        finally:
            await session.close()
    
    async def create_session(self) -> AsyncSession:
        """
        创建新的会话实例
        
        注意：调用者负责关闭会话
        """
        if not self._initialized:
            await self.initialize()
            
        return self.session_factory()
    
    async def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            async with self.get_session() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("Database connection test failed", error=str(e))
            return False
    
    async def close(self) -> None:
        """关闭数据库引擎"""
        if self.engine:
            await self.engine.dispose()
            logger.info("SessionManager closed")


# 全局会话管理器实例获取函数
async def get_session_manager() -> SessionManager:
    """获取会话管理器实例"""
    return await SessionManager.get_instance()


# 便捷的会话获取函数
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的便捷函数"""
    session_manager = await get_session_manager()
    async with session_manager.get_session() as session:
        yield session