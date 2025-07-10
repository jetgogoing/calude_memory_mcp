#!/usr/bin/env python3
"""
测试记忆注入集成功能
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType

async def setup_test_data():
    """创建测试数据"""
    print("初始化服务管理器...")
    service_manager = ServiceManager()
    
    try:
        await service_manager.start_service()
        print("服务启动成功！")
        
        # 创建测试对话
        print("\n创建测试对话数据...")
        
        # 测试对话 1：关于 Python 编程
        messages1 = [
            MessageModel(
                conversation_id="",
                message_type=MessageType.HUMAN,
                content="如何在 Python 中实现单例模式？",
                token_count=20
            ),
            MessageModel(
                conversation_id="",
                message_type=MessageType.ASSISTANT,
                content="在 Python 中实现单例模式有几种方法：\n1. 使用 __new__ 方法\n2. 使用装饰器\n3. 使用元类",
                token_count=50
            )
        ]
        
        conversation1 = ConversationModel(
            project_id="global",
            title="Python 单例模式讨论",
            messages=messages1,
            message_count=len(messages1),
            token_count=sum(m.token_count for m in messages1)
        )
        
        # 更新消息的 conversation_id
        for msg in messages1:
            msg.conversation_id = conversation1.id
        
        # 存储对话
        await service_manager._handle_new_conversation(conversation1)
        print(f"✓ 存储对话 1: {conversation1.title}")
        
        # 测试对话 2：关于 Claude Memory
        messages2 = [
            MessageModel(
                conversation_id="",
                message_type=MessageType.HUMAN,
                content="Claude Memory MCP 服务的核心功能是什么？",
                token_count=25
            ),
            MessageModel(
                conversation_id="",
                message_type=MessageType.ASSISTANT,
                content="Claude Memory MCP 服务的核心功能包括：\n1. 对话历史压缩和存储\n2. 语义搜索和记忆检索\n3. 上下文注入到新对话\n4. 全局记忆共享",
                token_count=80
            )
        ]
        
        conversation2 = ConversationModel(
            project_id="global",
            title="Claude Memory 功能介绍",
            messages=messages2,
            message_count=len(messages2),
            token_count=sum(m.token_count for m in messages2)
        )
        
        # 更新消息的 conversation_id
        for msg in messages2:
            msg.conversation_id = conversation2.id
        
        # 存储对话
        await service_manager._handle_new_conversation(conversation2)
        print(f"✓ 存储对话 2: {conversation2.title}")
        
        # 测试搜索功能
        print("\n测试搜索功能...")
        from claude_memory.models.data_models import SearchQuery
        
        search_query = SearchQuery(
            query="Python 单例模式",
            query_type="hybrid",
            limit=5,
            min_score=0.3
        )
        
        response = await service_manager.search_memories(search_query)
        print(f"✓ 搜索 'Python 单例模式' - 找到 {len(response.results)} 条结果")
        
        for idx, result in enumerate(response.results):
            print(f"  {idx+1}. {result.memory_unit.title} (相关度: {result.relevance_score:.2f})")
        
        # 测试注入功能
        print("\n测试记忆注入功能...")
        from claude_memory.models.data_models import ContextInjectionRequest
        
        injection_req = ContextInjectionRequest(
            original_prompt="我想了解如何实现单例模式",
            query_text="单例模式实现",
            injection_mode="balanced",
            max_tokens=2000
        )
        
        injection_response = await service_manager.inject_context(injection_req)
        print(f"✓ 注入成功！使用了 {injection_response.tokens_used} tokens")
        print(f"  注入了 {len(injection_response.injected_memories)} 条记忆")
        print(f"  处理时间: {injection_response.processing_time_ms:.1f}ms")
        
        print("\n增强后的提示：")
        print("-" * 50)
        print(injection_response.enhanced_prompt)
        print("-" * 50)
        
        print("\n✅ 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await service_manager.stop_service()
        print("\n服务已停止")

if __name__ == "__main__":
    asyncio.run(setup_test_data())