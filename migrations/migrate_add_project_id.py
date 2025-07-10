#!/usr/bin/env python3
"""
数据库迁移脚本：添加project_id字段
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from claude_memory.config.settings import get_settings

async def run_migration():
    """执行数据库迁移"""
    settings = get_settings()
    
    # 使用数据库连接URL
    db_url = settings.database.database_url
    
    print("🔄 开始数据库迁移...")
    
    try:
        # 连接数据库
        conn = await asyncpg.connect(db_url)
        
        # 读取SQL文件
        sql_file = Path(__file__).parent / "add_project_id_columns.sql"
        with open(sql_file, 'r') as f:
            sql_commands = f.read()
        
        # 执行迁移
        await conn.execute(sql_commands)
        
        # 验证迁移结果
        # 检查conversations表
        conv_columns = await conn.fetch("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'conversations' AND column_name = 'project_id'
        """)
        
        # 检查memory_units表
        mem_columns = await conn.fetch("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'memory_units' AND column_name = 'project_id'
        """)
        
        if conv_columns and mem_columns:
            print("✅ 成功添加project_id列到数据库表")
            print(f"   - conversations.project_id: {conv_columns[0]['data_type']}")
            print(f"   - memory_units.project_id: {mem_columns[0]['data_type']}")
        else:
            print("❌ 迁移可能失败，未找到project_id列")
            
        # 检查索引
        indexes = await conn.fetch("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename IN ('conversations', 'memory_units') 
            AND indexname LIKE '%project%'
        """)
        
        if indexes:
            print("✅ 成功创建project_id相关索引:")
            for idx in indexes:
                print(f"   - {idx['indexname']}")
        
        await conn.close()
        print("\n🎉 数据库迁移完成！")
        
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(run_migration())