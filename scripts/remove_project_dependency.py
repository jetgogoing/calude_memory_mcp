#!/usr/bin/env python3
"""
移除项目依赖 - 删除 projects 表并更新相关代码
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncpg
from claude_memory.config.settings import get_settings

async def remove_project_dependency():
    """移除项目依赖"""
    settings = get_settings()
    
    # 连接数据库
    conn = await asyncpg.connect(settings.database.database_url)
    
    try:
        print("=== 移除项目依赖 ===")
        
        # 1. 删除外键约束
        print("\n1. 删除外键约束...")
        
        # 删除 conversations 表的外键约束
        await conn.execute("""
            ALTER TABLE conversations 
            DROP CONSTRAINT IF EXISTS conversations_project_id_fkey CASCADE
        """)
        print("  - 已删除 conversations.project_id 外键")
        
        # 删除 memory_units 表的外键约束
        await conn.execute("""
            ALTER TABLE memory_units 
            DROP CONSTRAINT IF EXISTS memory_units_project_id_fkey CASCADE
        """)
        print("  - 已删除 memory_units.project_id 外键")
        
        # 2. 将 project_id 设为可空（作为过渡）
        print("\n2. 更新字段约束...")
        
        await conn.execute("""
            ALTER TABLE conversations 
            ALTER COLUMN project_id DROP NOT NULL
        """)
        print("  - conversations.project_id 已设为可空")
        
        await conn.execute("""
            ALTER TABLE memory_units 
            ALTER COLUMN project_id DROP NOT NULL
        """)
        print("  - memory_units.project_id 已设为可空")
        
        # 3. 删除 projects 表
        print("\n3. 删除 projects 表...")
        await conn.execute("DROP TABLE IF EXISTS projects CASCADE")
        print("  - projects 表已删除")
        
        # 4. 最终可以考虑完全删除 project_id 字段
        # 但为了向后兼容，暂时保留字段
        
        print("\n=== 数据库清理完成 ===")
        
        # 显示最终统计
        conv_count = await conn.fetchval("SELECT COUNT(*) FROM conversations")
        mem_count = await conn.fetchval("SELECT COUNT(*) FROM memory_units")
        
        print(f"\n最终数据统计：")
        print(f"- conversations: {conv_count} 条")
        print(f"- memory_units: {mem_count} 条")
        print(f"- projects 表已删除")
        print(f"- cost_tracking 表已删除")
        
    finally:
        await conn.close()


async def main():
    """主函数"""
    print("=== 项目依赖移除工具 ===")
    print("此工具将：")
    print("1. 删除外键约束")
    print("2. 删除 projects 表")
    print("3. 更新相关字段")
    
    print("\n开始执行...")
    await remove_project_dependency()


if __name__ == "__main__":
    asyncio.run(main())