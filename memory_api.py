#!/usr/bin/env python3
"""
Claude记忆管理 - 简单API接口
提供简单的记忆搜索和存储功能
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import SearchQuery, ConversationModel


class SimpleMemoryAPI:
    """简化的记忆管理API"""
    
    def __init__(self):
        self.service_manager = None
        self.initialized = False
    
    async def initialize(self):
        """初始化服务"""
        if self.initialized:
            return
            
        print("🔧 初始化记忆管理服务...")
        self.service_manager = ServiceManager()
        await self.service_manager._initialize_components()
        self.service_manager.is_running = True
        self.initialized = True
        print("✅ 记忆管理服务已就绪")
    
    async def search(self, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """搜索记忆"""
        if not self.initialized:
            await self.initialize()
        
        try:
            search_query = SearchQuery(
                query=query_text,
                query_type="hybrid",
                limit=limit,
                min_score=0.6,
                context=""
            )
            
            response = await self.service_manager.search_memories(search_query)
            
            # 简化返回结果
            results = []
            for result in response.results:
                results.append({
                    "title": result.memory_unit.title,
                    "summary": result.memory_unit.summary,
                    "score": result.relevance_score,
                    "keywords": result.memory_unit.keywords,
                    "created_at": result.memory_unit.created_at.isoformat()
                })
            
            return results
            
        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            return []
    
    async def add_conversation(self, messages: List[str], title: str = "对话记录") -> bool:
        """添加对话到记忆库"""
        if not self.initialized:
            await self.initialize()
        
        try:
            conversation = ConversationModel(
                title=title,
                messages=messages,
                participants=["user", "assistant"],
                message_count=len(messages),
                token_count=sum(len(msg.split()) * 1.3 for msg in messages)  # 粗略估算
            )
            
            await self.service_manager._handle_new_conversation(conversation)
            print(f"✅ 已保存对话: {title}")
            return True
            
        except Exception as e:
            print(f"❌ 保存对话失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        if self.service_manager:
            self.service_manager.is_running = False


# 全局API实例
memory_api = SimpleMemoryAPI()


def search_memory(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """同步搜索记忆 - 简单接口"""
    return asyncio.run(memory_api.search(query, limit))


def add_memory(messages: List[str], title: str = "对话记录") -> bool:
    """同步添加记忆 - 简单接口"""
    return asyncio.run(memory_api.add_conversation(messages, title))


async def test_api():
    """测试API功能"""
    print("🧪 测试记忆管理API...")
    
    # 初始化
    await memory_api.initialize()
    
    # 测试搜索
    print("\n🔍 测试搜索功能:")
    results = await memory_api.search("Python", limit=3)
    if results:
        print(f"找到 {len(results)} 条相关记忆:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result['title']} (相关度: {result['score']:.2f})")
    else:
        print("  暂无相关记忆")
    
    # 测试添加
    print("\n📝 测试添加记忆:")
    test_messages = [
        "用户: 如何使用Python创建异步函数?",
        "助手: 使用async def关键字可以创建异步函数，例如: async def my_function(): await some_task()"
    ]
    success = await memory_api.add_conversation(test_messages, "Python异步编程问答")
    print(f"  添加结果: {'成功' if success else '失败'}")
    
    await memory_api.cleanup()
    print("\n✅ API测试完成")


if __name__ == "__main__":
    print("Claude记忆管理 - 简单API")
    print("提供基础的搜索和存储功能\n")
    
    # 运行测试
    asyncio.run(test_api())
    
    print("\n📖 使用示例:")
    print("from memory_api import search_memory, add_memory")
    print("results = search_memory('你的搜索词')")
    print("add_memory(['消息1', '消息2'], '对话标题')")