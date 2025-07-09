#!/usr/bin/env python3
"""测试记忆系统并添加测试数据"""

import asyncio
import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_memory.core.memory_system import MemorySystem

async def main():
    print("测试Claude Memory系统...")
    
    # 初始化记忆系统
    memory_system = MemorySystem()
    await memory_system.initialize()
    
    # 获取状态
    status = await memory_system.get_status()
    print(f"\n系统状态: {status}")
    
    # 添加一些测试对话
    test_conversations = [
        {
            "type": "conversation",
            "timestamp": datetime.now().isoformat(),
            "content": "用户询问如何配置Claude Memory MCP服务",
            "response": "我帮您配置了混合MCP服务器，解决了TaskGroup错误，并实现了自动启动功能",
            "metadata": {
                "topic": "MCP配置",
                "importance": "high",
                "session": "session_1"
            }
        },
        {
            "type": "conversation", 
            "timestamp": datetime.now().isoformat(),
            "content": "用户遇到WSL2中Qdrant cgroups兼容性问题",
            "response": "通过Docker容器化解决了WSL2兼容性问题，升级到Qdrant v1.14.1",
            "metadata": {
                "topic": "WSL2兼容性",
                "importance": "high",
                "session": "session_2"
            }
        },
        {
            "type": "conversation",
            "timestamp": datetime.now().isoformat(),
            "content": "用户要求移除所有数据库密码",
            "response": "已更新配置文件，移除了所有数据库密码要求",
            "metadata": {
                "topic": "安全配置",
                "importance": "medium",
                "session": "session_2"
            }
        }
    ]
    
    # 保存测试对话
    print("\n添加测试对话...")
    for conv in test_conversations:
        result = await memory_system.save_memory(conv)
        print(f"- 保存: {conv['content'][:50]}... -> {result}")
    
    # 测试搜索
    print("\n测试搜索功能...")
    search_queries = ["MCP配置", "WSL2", "密码"]
    
    for query in search_queries:
        results = await memory_system.search_memories(query, limit=2)
        print(f"\n搜索 '{query}':")
        for i, result in enumerate(results):
            print(f"  {i+1}. 相似度: {result.get('score', 0):.3f}")
            print(f"     内容: {result.get('content', '')[:100]}...")
    
    # 再次获取状态
    final_status = await memory_system.get_status()
    print(f"\n最终状态: {final_status}")
    
    # 清理
    await memory_system.cleanup()

if __name__ == "__main__":
    asyncio.run(main())