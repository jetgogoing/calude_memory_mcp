#!/usr/bin/env python3
"""
检查数据库中的记忆单元
"""

import asyncio
import sys
import os
sys.path.insert(0, '/home/jetgogoing/claude_memory/src')

from claude_memory.database.session_manager import get_session_manager
from claude_memory.models.data_models import MemoryUnitDB

async def check_database():
    """检查数据库中的记忆单元"""
    
    session_manager = None
    try:
        # 获取数据库会话管理器
        session_manager = await get_session_manager()
        
        # 获取数据库会话
        async with session_manager.get_session() as session:
            # 查询所有记忆单元
            from sqlalchemy import select
            result = await session.execute(select(MemoryUnitDB))
            memory_units = result.scalars().all()
            
            print(f"=== 数据库中的记忆单元总数: {len(memory_units)} ===")
            
            if memory_units:
                for i, unit in enumerate(memory_units[:10]):  # 显示前10个
                    print(f"\n{i+1}. ID: {unit.id}")
                    print(f"   标题: {unit.title}")
                    print(f"   摘要: {unit.summary[:100]}...")
                    print(f"   关键词: {unit.keywords}")
                    print(f"   创建时间: {unit.created_at}")
                    print(f"   活跃状态: {unit.is_active}")
                
                # 搜索包含"星云智能"的记忆
                print("\n=== 搜索包含'星云智能'的记忆 ===")
                nebula_units = [unit for unit in memory_units if 
                               "星云智能" in unit.title or 
                               "星云智能" in unit.summary or 
                               "星云智能" in unit.content or
                               (unit.keywords and "星云智能" in str(unit.keywords))]
                
                if nebula_units:
                    print(f"找到 {len(nebula_units)} 条相关记忆:")
                    for unit in nebula_units:
                        print(f"  - {unit.title}: {unit.summary[:50]}...")
                else:
                    print("未找到包含'星云智能'的记忆")
                    
                    # 搜索相关关键词
                    print("\n=== 搜索相关关键词 ===")
                    related_units = [unit for unit in memory_units if 
                                    any(keyword in unit.title.lower() or 
                                        keyword in unit.summary.lower() or 
                                        keyword in unit.content.lower()
                                        for keyword in ["智能", "AI", "nebula", "星云"])]
                    
                    if related_units:
                        print(f"找到 {len(related_units)} 条相关记忆:")
                        for unit in related_units[:5]:
                            print(f"  - {unit.title}: {unit.summary[:50]}...")
                    else:
                        print("未找到相关记忆")
            else:
                print("数据库中没有记忆单元")
                
    except Exception as e:
        print(f"❌ 检查数据库失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if session_manager:
            await session_manager.close()

if __name__ == "__main__":
    asyncio.run(check_database())