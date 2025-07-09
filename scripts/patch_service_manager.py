#!/usr/bin/env python3
"""
修复ServiceManager，确保在存储记忆时自动创建项目
"""

import os
import sys

def create_patch():
    """创建补丁文件"""
    patch_content = '''--- a/src/claude_memory/managers/service_manager.py
+++ b/src/claude_memory/managers/service_manager.py
@@ -461,6 +461,11 @@ class ServiceManager:
             # 首先存储对话到PostgreSQL
             from claude_memory.database.session_manager import get_db_session
             from claude_memory.models.data_models import ConversationDB, MessageDB, MemoryUnitDB
+            
+            # 确保项目存在
+            if self.project_manager and conversation.project_id:
+                self.project_manager.get_or_create_project(
+                    conversation.project_id)
             
             async with get_db_session() as session:
                 # 创建对话记录
@@ -588,6 +593,11 @@ class ServiceManager:
         try:
             # 首先保存到PostgreSQL
             async with get_db_session() as session:
+                # 确保项目存在
+                if self.project_manager and memory_unit.project_id:
+                    self.project_manager.get_or_create_project(
+                        memory_unit.project_id)
+                
                 # 检查对话是否存在
                 from ..models.data_models import ConversationDB
                 existing_conv = await session.get(ConversationDB, memory_unit.conversation_id)
'''
    
    # 写入补丁文件
    patch_file = "fix_project_creation.patch"
    with open(patch_file, 'w') as f:
        f.write(patch_content)
    
    print(f"补丁文件已创建: {patch_file}")
    print("\n应用补丁的命令:")
    print(f"  patch -p1 < {patch_file}")
    print("\n或者使用git apply:")
    print(f"  git apply {patch_file}")
    
    return patch_file

def apply_patch_manually():
    """手动应用补丁"""
    file_path = "src/claude_memory/managers/service_manager.py"
    
    # 读取文件
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 查找插入点1 - _handle_new_conversation方法
    insert_point1 = content.find("            # 首先存储对话到PostgreSQL")
    if insert_point1 != -1:
        # 找到下一行的位置
        next_line1 = content.find("\n", insert_point1) + 1
        next_line1 = content.find("\n", next_line1) + 1  # 跳过import行
        next_line1 = content.find("\n", next_line1) + 1  # 跳过第二个import行
        
        # 插入代码
        insert_code1 = """            
            # 确保项目存在
            if self.project_manager and conversation.project_id:
                self.project_manager.get_or_create_project(
                    conversation.project_id)
"""
        content = content[:next_line1] + insert_code1 + content[next_line1:]
    
    # 查找插入点2 - add_memory方法
    insert_point2 = content.find("            # 首先保存到PostgreSQL")
    if insert_point2 != -1:
        # 找到async with行
        async_with_pos = content.find("async with get_db_session()", insert_point2)
        if async_with_pos != -1:
            next_line2 = content.find("\n", async_with_pos) + 1
            
            # 插入代码
            insert_code2 = """                # 确保项目存在
                if self.project_manager and memory_unit.project_id:
                    self.project_manager.get_or_create_project(
                        memory_unit.project_id)
                
"""
            content = content[:next_line2] + insert_code2 + content[next_line2:]
    
    # 备份原文件
    backup_path = file_path + ".backup"
    with open(file_path, 'r') as f:
        backup_content = f.read()
    with open(backup_path, 'w') as f:
        f.write(backup_content)
    
    # 写入修改后的内容
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✓ 已修改文件: {file_path}")
    print(f"✓ 备份文件: {backup_path}")

def main():
    """主函数"""
    print("=== ServiceManager 项目自动创建补丁 ===\n")
    
    # 创建补丁文件
    patch_file = create_patch()
    
    # 询问是否直接应用
    response = input("\n是否直接应用补丁到代码? (y/n): ")
    if response.lower() == 'y':
        try:
            apply_patch_manually()
            print("\n✓ 补丁应用成功!")
            print("请重启服务以使更改生效。")
        except Exception as e:
            print(f"\n✗ 补丁应用失败: {e}")
            print("请手动检查和应用补丁。")
    else:
        print("\n请手动应用补丁。")

if __name__ == "__main__":
    main()