#!/usr/bin/env python3
"""
直接测试MCP服务器的无感记忆注入
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, '/home/jetgogoing/claude_memory/src')

from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import SearchQuery, ContextInjectionRequest

async def test_mcp_direct():
    """直接测试MCP服务器"""
    
    # 创建服务管理器
    service_manager = ServiceManager()
    
    try:
        # 启动服务
        await service_manager.start_service()
        
        # 测试1：直接搜索
        print("=== 测试1：直接搜索'星云智能' ===")
        search_query = SearchQuery(
            query="星云智能",
            query_type="hybrid",
            limit=5,
            min_score=0.0,  # 设置为0来查看所有结果
            context=""
        )
        
        search_response = await service_manager.search_memories(search_query)
        
        print(f"搜索结果数量: {len(search_response.results)}")
        print(f"总找到数量: {search_response.total_count}")
        print(f"搜索时间: {search_response.search_time_ms}ms")
        
        if search_response.results:
            print("找到的记忆:")
            for i, result in enumerate(search_response.results):
                print(f"{i+1}. {result.memory_unit.title}")
                print(f"   评分: {result.relevance_score}")
                print(f"   摘要: {result.memory_unit.summary[:100]}...")
                print()
        else:
            print("未找到任何记忆")
        
        # 测试2：上下文注入
        print("=== 测试2：上下文注入 ===")
        injection_request = ContextInjectionRequest(
            original_prompt="星云智能你有印象吗？",
            query_text="星云智能",
            context_hint="",
            injection_mode="comprehensive",
            max_tokens=999999
        )
        
        injection_response = await service_manager.inject_context(injection_request)
        
        print(f"注入记忆数量: {len(injection_response.injected_memories)}")
        print(f"增强后的prompt长度: {len(injection_response.enhanced_prompt)} 字符")
        print(f"处理时间: {injection_response.processing_time_ms}ms")
        
        if injection_response.injected_memories:
            print("✅ 成功注入历史记忆:")
            for memory in injection_response.injected_memories:
                print(f"  - {memory.title}: {memory.summary[:50]}...")
            
            # 检查增强后的prompt
            original_len = len(injection_request.original_prompt)
            enhanced_len = len(injection_response.enhanced_prompt)
            
            if enhanced_len > original_len:
                print(f"✅ 无感记忆注入成功！增强后的prompt比原始prompt长了 {enhanced_len - original_len} 字符")
                print("\n增强后的prompt预览:")
                print(injection_response.enhanced_prompt[:200] + "...")
            else:
                print("❌ 虽然找到了记忆，但prompt未被增强")
        else:
            print("❌ 未找到相关历史记忆")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 停止服务
        await service_manager.stop_service()

if __name__ == "__main__":
    asyncio.run(test_mcp_direct())