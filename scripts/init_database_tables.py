#!/usr/bin/env python3
"""
Claude Memory MCP Service - 初始化数据库表结构

创建所有必要的数据库表。
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from sqlalchemy import create_engine
from claude_memory.models.data_models import Base
from claude_memory.config.settings import get_settings


def init_database():
    """初始化数据库表结构"""
    settings = get_settings()
    
    # 创建数据库引擎
    engine = create_engine(
        settings.database.database_url,
        echo=True,  # 打印SQL语句
        pool_pre_ping=True
    )
    
    print("🔄 正在创建数据库表结构...")
    
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库表创建成功！")
        
        # 列出所有创建的表
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print("\n📊 已创建的表：")
        for table in tables:
            print(f"  - {table}")
            
        print(f"\n总计: {len(tables)} 个表")
        
    except Exception as e:
        print(f"❌ 创建数据库表失败: {e}")
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    init_database()