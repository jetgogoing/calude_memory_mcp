#!/usr/bin/env python3
"""手动创建数据库表"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# 设置环境变量
os.environ["DATABASE_URL"] = "postgresql://claude_memory:password@localhost:5432/claude_memory"

from sqlalchemy import create_engine, text
from claude_memory.models.data_models import Base
from claude_memory.config.settings import get_settings

def create_tables():
    """创建所有表"""
    settings = get_settings()
    
    # 创建同步引擎
    sync_url = settings.database.database_url.replace("+asyncpg", "")
    engine = create_engine(sync_url, echo=True)
    
    print("🔄 开始创建数据库表...")
    
    try:
        # 删除所有现有表（谨慎！）
        Base.metadata.drop_all(bind=engine)
        print("✅ 已删除所有现有表")
        
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("✅ 已创建所有表")
        
        # 验证表是否创建成功
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            
            print("\n📊 数据库中的表：")
            for table in tables:
                print(f"  - {table}")
            print(f"\n总计: {len(tables)} 个表")
            
            # 创建默认项目
            if 'projects' in tables:
                conn.execute(text("""
                    INSERT INTO projects (id, name, description, is_active, created_at, updated_at)
                    VALUES ('default', 'Default Project', 'Default project for Claude Memory', true, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """))
                conn.commit()
                print("\n✅ 已创建默认项目")
    
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_tables()