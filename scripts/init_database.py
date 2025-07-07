#!/usr/bin/env python3
"""
Claude记忆管理MCP服务 - 数据库初始化脚本

功能：
1. 创建所有数据库表
2. 验证数据库连接
3. 初始化基础数据
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from claude_memory.config.settings import get_settings
from claude_memory.models.data_models import Base

async def init_database():
    """初始化数据库"""
    settings = get_settings()
    
    print(f"Initializing database: {settings.database.database_url}")
    
    if settings.database.database_url.startswith("sqlite"):
        # SQLite异步连接
        database_url = settings.database.database_url.replace("sqlite://", "sqlite+aiosqlite://")
        engine = create_async_engine(database_url)
    else:
        # PostgreSQL异步连接
        database_url = settings.database.database_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(database_url)
    
    print(f"Using database URL: {database_url}")
    
    try:
        async with engine.begin() as conn:
            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
            print("✅ All tables created successfully")
        
        # 验证表是否存在
        async with engine.begin() as conn:
            from sqlalchemy import text
            query = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'") \
                    if not database_url.startswith("sqlite") \
                    else text("SELECT name FROM sqlite_master WHERE type='table'")
            result = await conn.execute(query)
            tables = [row[0] for row in result.fetchall()]
            print(f"✅ Tables found: {', '.join(tables)}")
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    # 确保使用正确的环境变量
    import os
    if "DATABASE__DATABASE_URL" not in os.environ:
        os.environ["DATABASE__DATABASE_URL"] = "postgresql://claude_memory:password@localhost:5432/claude_memory_db"
    
    asyncio.run(init_database())