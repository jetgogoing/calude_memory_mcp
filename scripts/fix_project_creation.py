#!/usr/bin/env python3
"""
修复项目创建问题 - 确保在存储记忆单元时自动创建项目
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.claude_memory.database.sync_session import get_sync_session
from src.claude_memory.models.data_models import ProjectDB, MemoryUnitDB, ConversationDB
from src.claude_memory.managers.project_manager import get_project_manager
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

def main():
    """主函数"""
    project_manager = get_project_manager()
    
    # 1. 首先检查是否有孤儿记忆单元（项目不存在）
    with get_sync_session() as session:
        # 获取所有记忆单元使用的项目ID
        memory_project_ids = session.query(MemoryUnitDB.project_id).distinct().all()
        memory_project_ids = [pid[0] for pid in memory_project_ids]
        
        # 获取所有对话使用的项目ID
        conv_project_ids = session.query(ConversationDB.project_id).distinct().all()
        conv_project_ids = [pid[0] for pid in conv_project_ids]
        
        # 合并所有项目ID
        all_used_project_ids = set(memory_project_ids + conv_project_ids)
        
        # 获取现有项目
        existing_projects = session.query(ProjectDB.id).all()
        existing_project_ids = set([p[0] for p in existing_projects])
        
        # 找出缺失的项目
        missing_project_ids = all_used_project_ids - existing_project_ids
        
        print(f"=== 项目检查结果 ===")
        print(f"记忆单元使用的项目: {memory_project_ids}")
        print(f"对话使用的项目: {conv_project_ids}")
        print(f"现有项目: {list(existing_project_ids)}")
        print(f"缺失的项目: {list(missing_project_ids)}")
        
        # 2. 为缺失的项目创建记录
        if missing_project_ids:
            print(f"\n=== 创建缺失的项目 ===")
            for project_id in missing_project_ids:
                try:
                    # 获取该项目的记忆单元数量
                    memory_count = session.query(MemoryUnitDB).filter_by(project_id=project_id).count()
                    conv_count = session.query(ConversationDB).filter_by(project_id=project_id).count()
                    
                    # 创建项目
                    project = project_manager.create_project(
                        project_id=project_id,
                        name=f"项目 {project_id}",
                        description=f"自动恢复的项目 - 包含 {memory_count} 条记忆和 {conv_count} 个对话"
                    )
                    print(f"✓ 创建项目: {project_id} (记忆: {memory_count}, 对话: {conv_count})")
                except Exception as e:
                    print(f"✗ 创建项目 {project_id} 失败: {e}")
        else:
            print("\n所有项目都已存在，无需创建")
        
        # 3. 显示最终统计
        print(f"\n=== 最终统计 ===")
        final_projects = session.query(ProjectDB).all()
        for project in final_projects:
            memory_count = session.query(MemoryUnitDB).filter_by(project_id=project.id).count()
            conv_count = session.query(ConversationDB).filter_by(project_id=project.id).count()
            print(f"项目: {project.id}")
            print(f"  - 名称: {project.name}")
            print(f"  - 记忆单元: {memory_count}")
            print(f"  - 对话: {conv_count}")
            print(f"  - 激活状态: {project.is_active}")
            print()

if __name__ == "__main__":
    main()