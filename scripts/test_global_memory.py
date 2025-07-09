#!/usr/bin/env python3
"""
Claude Memory 全局服务验证脚本
用于测试记忆是否能跨项目共享
"""

import os
import sys
import uuid
import json
import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_memory.models.data_models import MemoryUnit, ConversationTurn
from claude_memory.database.manager import DatabaseManager
from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.utils.error_handling import ErrorHandler

# 生成测试标识
TEST_RUN_ID = str(uuid.uuid4())[:8]
TEST_MARKER = f"GLOBAL_TEST_{TEST_RUN_ID}"
TEST_USER_ID = f"test_user_{TEST_RUN_ID}"
TEST_PROJECT_ID = os.environ.get("CLAUDE_MEMORY_PROJECT_ID", "claude_memory")

print(f"""
═══════════════════════════════════════════════════════════════════
🧪 Claude Memory 全局服务验证测试
═══════════════════════════════════════════════════════════════════
测试ID: {TEST_RUN_ID}
测试标记: {TEST_MARKER}
测试用户: {TEST_USER_ID}
当前项目: {TEST_PROJECT_ID}
═══════════════════════════════════════════════════════════════════
""")

def create_test_memories():
    """创建带标记的测试记忆"""
    print("\n📝 步骤1: 创建测试记忆...")
    
    try:
        # 初始化数据库管理器
        db_manager = DatabaseManager()
        
        # 创建测试对话数据
        test_conversations = [
            {
                "role": "user",
                "content": f"[{TEST_MARKER}] 这是一条来自项目 {TEST_PROJECT_ID} 的测试消息。当前时间: {datetime.datetime.now().isoformat()}"
            },
            {
                "role": "assistant", 
                "content": f"[{TEST_MARKER}] 我已经收到您的测试消息。这条记忆应该能在其他项目中被检索到。"
            },
            {
                "role": "user",
                "content": f"[{TEST_MARKER}] 请记住这个秘密代码: ALPHA-{TEST_RUN_ID}-OMEGA"
            },
            {
                "role": "assistant",
                "content": f"[{TEST_MARKER}] 我已经记住了秘密代码 ALPHA-{TEST_RUN_ID}-OMEGA。这个记忆将被存储在全局服务中。"
            }
        ]
        
        # 转换为 ConversationTurn 对象
        conversation_turns = []
        for idx, turn in enumerate(test_conversations):
            conversation_turn = ConversationTurn(
                role=turn["role"],
                content=turn["content"],
                timestamp=datetime.datetime.now()
            )
            conversation_turns.append(conversation_turn)
        
        # 创建记忆单元
        memory_unit = MemoryUnit(
            user_id=TEST_USER_ID,
            project_id=TEST_PROJECT_ID,
            conversation_id=f"test_conv_{TEST_RUN_ID}",
            conversation_turns=conversation_turns,
            summary=f"测试对话 - 包含标记 {TEST_MARKER} 和秘密代码",
            importance_score=0.9,  # 高重要性确保被记住
            memory_type="TEST",
            keywords=[TEST_MARKER, "test", "global", "verification", TEST_RUN_ID],
            test_marker=TEST_MARKER  # 额外的标记字段
        )
        
        # 存储到数据库
        stored_memory = db_manager.store_memory_unit(memory_unit)
        print(f"✅ 成功存储测试记忆，ID: {stored_memory.id}")
        
        # 验证存储
        retrieved = db_manager.get_memory_by_id(stored_memory.id)
        if retrieved:
            print(f"✅ 验证：记忆已成功存储在数据库中")
            print(f"   - 项目ID: {retrieved.project_id}")
            print(f"   - 用户ID: {retrieved.user_id}")
            print(f"   - 摘要: {retrieved.summary}")
        
        # 保存测试信息供后续验证
        test_info = {
            "test_run_id": TEST_RUN_ID,
            "test_marker": TEST_MARKER,
            "test_user_id": TEST_USER_ID,
            "memory_id": str(stored_memory.id),
            "project_id": TEST_PROJECT_ID,
            "secret_code": f"ALPHA-{TEST_RUN_ID}-OMEGA",
            "created_at": datetime.datetime.now().isoformat()
        }
        
        test_info_path = Path.home() / ".claude_memory_test_info.json"
        with open(test_info_path, "w") as f:
            json.dump(test_info, f, indent=2)
        
        print(f"\n📄 测试信息已保存到: {test_info_path}")
        print(f"   请在其他项目中运行验证脚本来检查记忆是否可访问")
        
        return True
        
    except Exception as e:
        ErrorHandler.log_error(e, "创建测试记忆失败")
        print(f"❌ 错误: {str(e)}")
        return False

def search_test_memories(test_marker=None):
    """搜索测试记忆"""
    print(f"\n🔍 搜索记忆（标记: {test_marker or '从文件读取'}）...")
    
    try:
        # 如果没有提供标记，从文件读取
        if not test_marker:
            test_info_path = Path.home() / ".claude_memory_test_info.json"
            if test_info_path.exists():
                with open(test_info_path, "r") as f:
                    test_info = json.load(f)
                    test_marker = test_info["test_marker"]
                    print(f"📄 从文件读取测试信息:")
                    print(f"   - 测试标记: {test_marker}")
                    print(f"   - 原始项目: {test_info['project_id']}")
                    print(f"   - 秘密代码: {test_info['secret_code']}")
            else:
                print("❌ 未找到测试信息文件，请先运行创建测试")
                return False
        
        # 初始化检索器
        retriever = SemanticRetriever()
        
        # 搜索包含测试标记的记忆
        print(f"\n🔎 搜索包含 '{test_marker}' 的记忆...")
        results = retriever.search(
            query=test_marker,
            user_id=None,  # 不限制用户，测试全局访问
            limit=10
        )
        
        if results:
            print(f"\n✅ 找到 {len(results)} 条相关记忆:")
            for idx, memory in enumerate(results, 1):
                print(f"\n--- 记忆 {idx} ---")
                print(f"ID: {memory.id}")
                print(f"项目: {memory.project_id}")
                print(f"用户: {memory.user_id}")
                print(f"摘要: {memory.summary}")
                print(f"重要性: {memory.importance_score}")
                
                # 检查是否包含测试标记
                content_has_marker = any(
                    test_marker in turn.content 
                    for turn in memory.conversation_turns
                )
                if content_has_marker:
                    print(f"✅ 确认：包含测试标记 {test_marker}")
                    
                    # 显示对话内容
                    print("\n对话内容:")
                    for turn in memory.conversation_turns:
                        print(f"  [{turn.role}]: {turn.content[:100]}...")
                        
            return True
        else:
            print(f"❌ 未找到包含标记 '{test_marker}' 的记忆")
            return False
            
    except Exception as e:
        ErrorHandler.log_error(e, "搜索测试记忆失败")
        print(f"❌ 错误: {str(e)}")
        return False

def cleanup_test_memories():
    """清理测试数据"""
    print("\n🧹 清理测试数据...")
    
    try:
        test_info_path = Path.home() / ".claude_memory_test_info.json"
        if test_info_path.exists():
            with open(test_info_path, "r") as f:
                test_info = json.load(f)
            
            db_manager = DatabaseManager()
            
            # 删除测试记忆
            if "memory_id" in test_info:
                success = db_manager.delete_memory(test_info["memory_id"])
                if success:
                    print(f"✅ 已删除测试记忆: {test_info['memory_id']}")
                else:
                    print(f"⚠️  无法删除测试记忆: {test_info['memory_id']}")
            
            # 删除测试信息文件
            test_info_path.unlink()
            print("✅ 已删除测试信息文件")
            
            return True
        else:
            print("ℹ️  未找到测试数据")
            return True
            
    except Exception as e:
        ErrorHandler.log_error(e, "清理测试数据失败")
        print(f"❌ 错误: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Memory 全局服务验证测试")
    parser.add_argument("action", choices=["create", "search", "cleanup"], 
                       help="要执行的操作")
    parser.add_argument("--marker", help="测试标记（仅用于搜索）")
    
    args = parser.parse_args()
    
    if args.action == "create":
        success = create_test_memories()
        if success:
            print("\n✅ 测试记忆创建成功！")
            print("👉 请切换到其他项目运行: python test_global_memory.py search")
    
    elif args.action == "search":
        success = search_test_memories(args.marker)
        if success:
            print("\n✅ 全局记忆验证成功！")
        else:
            print("\n❌ 全局记忆验证失败")
    
    elif args.action == "cleanup":
        success = cleanup_test_memories()
        if success:
            print("\n✅ 清理完成")
            
    sys.exit(0 if success else 1)