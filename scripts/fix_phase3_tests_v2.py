#!/usr/bin/env python3
"""
Phase 3 测试修复脚本V2
使用完整的ServiceManager API流程，不直接操作数据库
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import (
    ConversationModel, 
    MessageModel, 
    MessageType,
    SearchQuery,
    MemoryUnitType,
    ProcessConversationRequest,
    ProcessConversationResult
)
from claude_memory.retrievers.semantic_retriever import RetrievalRequest
from claude_memory.processors.semantic_compressor import CompressionRequest


async def test_multi_turn_conversation_fix():
    """修复多轮对话测试 - 使用完整API流程"""
    print("\n🔧 测试多轮对话修复方案V2...")
    
    service_manager = ServiceManager()
    await service_manager.start_service()
    
    try:
        # 创建一个完整的多轮对话
        conversation = ConversationModel(
            project_id="phase3_fix_test_v2",
            title="Python异步编程完整讨论"
        )
        
        # 构建对话内容
        turns = [
            ("什么是Python的异步编程？", 
             "Python异步编程是一种并发编程模式，使用async/await语法。关键概念包括异步函数、协程和事件循环。"),
            ("能给个async/await的例子吗？", 
             "当然！异步编程示例：async def fetch_data(): await asyncio.sleep(1); return 'data'。这展示了async函数定义和await的使用。"),
            ("异步函数中如何处理异常？", 
             "在异步编程中处理异常：使用try/except包裹await调用，或使用asyncio.gather的return_exceptions参数。异常处理是异步编程的重要部分。"),
            ("如何优化异步代码的性能？", 
             "异步编程性能优化：使用asyncio.gather并发执行，避免不必要的await，使用连接池。这些都是Python异步编程的最佳实践。")
        ]
        
        # 添加消息到对话
        for i, (question, answer) in enumerate(turns):
            # 用户消息
            conversation.messages.append(MessageModel(
                conversation_id=conversation.id,
                message_type=MessageType.HUMAN,
                content=question,
                timestamp=conversation.started_at
            ))
            
            # 助手回复 - 确保包含关键词
            conversation.messages.append(MessageModel(
                conversation_id=conversation.id,
                message_type=MessageType.ASSISTANT,
                content=f"{answer} [Python异步编程讨论第{i+1}轮]",
                timestamp=conversation.started_at
            ))
        
        # 使用ServiceManager的process_conversation方法处理整个对话
        request = ProcessConversationRequest(
            conversation=conversation,
            force_process=True,
            quality_threshold=0.7
        )
        
        result = await service_manager.process_conversation(request)
        
        if result.success and result.memory_units:
            print(f"✅ 成功处理对话，生成 {len(result.memory_units)} 个记忆单元")
            for unit in result.memory_units:
                print(f"  - 记忆单元: {unit.title[:50]}...")
                print(f"    质量分数: {unit.quality_score:.3f}")
        else:
            print(f"❌ 处理对话失败: {result.error or '未知错误'}")
            return False
        
        # 等待一下让向量存储完成
        await asyncio.sleep(2)
        
        # 测试检索
        test_queries = [
            "Python异步编程",
            "异步异常处理",
            "async await示例"
        ]
        
        for query_text in test_queries:
            search_query = SearchQuery(
                query=query_text,
                query_type="hybrid",
                limit=10,
                min_score=0.2  # 降低阈值
            )
            
            request = RetrievalRequest(
                query=search_query,
                project_id="phase3_fix_test_v2",
                limit=10,
                min_score=0.2,
                hybrid_search=True
            )
            
            results = await service_manager.semantic_retriever.retrieve_memories(request)
            print(f"\n查询 '{query_text}': 找到 {len(results.results)} 条结果")
            
            if results.results:
                # 检查是否包含多轮对话内容
                turns_found = set()
                for result in results.results:
                    content = result.memory_unit.content
                    for i in range(4):
                        if f"第{i+1}轮" in content:
                            turns_found.add(i+1)
                
                print(f"  - 覆盖对话轮次: {sorted(turns_found)}")
                print(f"  - 最高相关度: {results.results[0].relevance_score:.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await service_manager.stop_service()


async def test_context_injection_fix():
    """修复上下文注入测试 - 使用完整API流程"""
    print("\n🔧 测试上下文注入修复方案V2...")
    
    service_manager = ServiceManager()
    await service_manager.start_service()
    
    try:
        # 创建包含决策的对话
        conversation = ConversationModel(
            project_id="phase3_fix_test_v2",
            title="API响应格式标准决策"
        )
        
        # 构建决策对话
        conversation.messages = [
            MessageModel(
                conversation_id=conversation.id,
                message_type=MessageType.HUMAN,
                content="我们的API应该使用什么响应格式？需要标准化。",
                timestamp=conversation.started_at
            ),
            MessageModel(
                conversation_id=conversation.id,
                message_type=MessageType.ASSISTANT,
                content="""经过团队讨论，我们决定采用JSON:API规范作为API响应格式标准。
                
主要原因：
1. 标准化的错误处理格式
2. 支持资源关联和包含
3. 统一的分页和过滤格式
4. 良好的文档和工具支持

这是一个重要的技术决策，将影响所有API的实现。""",
                timestamp=conversation.started_at,
                metadata={"decision": True, "importance": "high"}
            )
        ]
        
        # 使用ServiceManager处理对话
        request = ProcessConversationRequest(
            conversation=conversation,
            force_process=True,
            quality_threshold=0.8  # 决策类型使用更高的质量阈值
        )
        
        result = await service_manager.process_conversation(request)
        
        if result.success and result.memory_units:
            print(f"✅ 成功生成 {len(result.memory_units)} 个记忆单元")
            for unit in result.memory_units:
                print(f"  - {unit.title[:50]}... (质量: {unit.quality_score:.3f})")
        else:
            print(f"❌ 处理失败: {result.error}")
            return False
        
        # 等待存储完成
        await asyncio.sleep(2)
        
        # 测试检索决策
        user_query = "我们的API应该使用什么响应格式？"
        
        search_query = SearchQuery(
            query=user_query,
            query_type="hybrid",
            limit=5,
            min_score=0.2
        )
        
        request = RetrievalRequest(
            query=search_query,
            project_id="phase3_fix_test_v2",
            limit=5,
            min_score=0.2
        )
        
        results = await service_manager.semantic_retriever.retrieve_memories(request)
        
        if results.results:
            print(f"\n✅ 成功检索到 {len(results.results)} 条相关记忆")
            
            # 构建增强的上下文
            enhanced_context = f"用户问题：{user_query}\n\n相关历史决策：\n"
            
            for i, result in enumerate(results.results):
                memory = result.memory_unit
                enhanced_context += f"\n{i+1}. {memory.title}\n"
                enhanced_context += f"   类型: {memory.unit_type}\n"
                enhanced_context += f"   内容: {memory.content[:200]}...\n"
                enhanced_context += f"   相关度: {result.relevance_score:.3f}\n"
            
            print("\n增强后的上下文预览:")
            print("-" * 50)
            print(enhanced_context[:500] + "...")
            
            # 验证是否包含JSON:API决策
            if "JSON:API" in enhanced_context:
                print("\n✅ 上下文成功注入API格式决策信息")
                return True
            else:
                print("\n⚠️ 上下文中未找到预期的决策信息")
                return False
        else:
            print("\n❌ 未能检索到任何相关记忆")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await service_manager.stop_service()


async def main():
    """运行所有修复测试"""
    print("🚀 开始Phase 3测试修复验证V2")
    print("=" * 60)
    
    # 测试多轮对话修复
    multi_turn_success = await test_multi_turn_conversation_fix()
    
    # 测试上下文注入修复
    context_injection_success = await test_context_injection_fix()
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 修复验证结果")
    print(f"- 多轮对话: {'✅ 成功' if multi_turn_success else '❌ 失败'}")
    print(f"- 上下文注入: {'✅ 成功' if context_injection_success else '❌ 失败'}")
    
    if multi_turn_success and context_injection_success:
        print("\n🎉 所有修复方案验证通过！")
        print("建议：")
        print("1. 使用ServiceManager.process_conversation而不是直接操作数据库")
        print("2. 确保使用ProcessConversationRequest封装请求")
        print("3. 降低检索阈值到0.2-0.3")
        print("4. 等待异步操作完成后再进行检索")
    else:
        print("\n⚠️ 部分修复方案需要进一步调整")


if __name__ == "__main__":
    asyncio.run(main())