#!/usr/bin/env python3
"""
测试无感记忆注入功能
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, '/home/jetgogoing/claude_memory/src')

from claude_memory.mcp_server import ClaudeMemoryMCPServer

async def test_seamless_injection():
    """测试无感记忆注入"""
    
    # 创建MCP服务器实例
    mcp_server = ClaudeMemoryMCPServer()
    
    try:
        # 初始化服务器
        await mcp_server.initialize()
        
        # 测试1：搜索"星云智能"
        print("=== 测试1：搜索'星云智能' ===")
        search_args = {
            "query": "星云智能",
            "limit": 5,
            "min_score": 0.0  # 设置为0来查看所有结果
        }
        
        results = await mcp_server._handle_search(search_args)
        if results:
            result_text = results[0].text
            result_data = json.loads(result_text)
            print(f"搜索结果: {result_data.get('total_found', 0)} 条")
            if result_data.get('results'):
                for result in result_data['results'][:3]:
                    print(f"  - {result['title']}: {result['summary'][:50]}...")
        
        # 测试2：无感记忆注入
        print("\n=== 测试2：无感记忆注入 ===")
        inject_args = {
            "original_prompt": "星云智能你有印象吗？",
            "injection_mode": "comprehensive",
            "max_tokens": 999999
        }
        
        inject_results = await mcp_server._handle_inject(inject_args)
        if inject_results:
            inject_text = inject_results[0].text
            inject_data = json.loads(inject_text)
            
            if inject_data.get('success'):
                enhanced_prompt = inject_data.get('enhanced_prompt', '')
                injected_memories = inject_data.get('injected_memories', [])
                
                print(f"注入记忆数量: {len(injected_memories)}")
                print(f"增强后的prompt长度: {len(enhanced_prompt)} 字符")
                
                # 检查是否真的注入了记忆
                if injected_memories:
                    print("✅ 成功注入历史记忆:")
                    for memory in injected_memories[:3]:
                        print(f"  - {memory['title']}: {memory['summary'][:50]}...")
                    
                    # 验证增强后的prompt包含历史信息
                    if len(enhanced_prompt) > len(inject_args['original_prompt']):
                        print("✅ 无感记忆注入成功！增强后的prompt包含历史上下文")
                    else:
                        print("❌ 虽然找到了记忆，但prompt未被增强")
                else:
                    print("❌ 未找到相关历史记忆")
            else:
                print(f"❌ 注入失败: {inject_data.get('error', 'Unknown error')}")
        
        # 测试3：健康检查
        print("\n=== 测试3：健康检查 ===")
        health_results = await mcp_server._handle_health({"detailed": True})
        if health_results:
            health_text = health_results[0].text
            health_data = json.loads(health_text)
            print(f"健康状态: {health_data.get('health_status', 'Unknown')}")
            if health_data.get('issues'):
                print(f"发现问题: {health_data['issues']}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理
        await mcp_server.cleanup()

if __name__ == "__main__":
    asyncio.run(test_seamless_injection())