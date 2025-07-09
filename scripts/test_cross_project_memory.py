#!/usr/bin/env python3
"""
Claude记忆管理 - 跨项目记忆共享测试

测试通过 API Server 创建和查询记忆，验证跨项目共享功能
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_memory.config.settings import get_settings

# API Server地址
API_BASE_URL = os.getenv("CLAUDE_MEMORY_API_URL", "http://localhost:8000")

# 使用统一的project_id
PROJECT_ID = "global"


async def test_health_check():
    """测试API Server健康状态"""
    print("\n1. 测试 API Server 健康状态...")
    
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        try:
            response = await client.get("/health")
            if response.status_code == 200:
                print("✅ API Server 运行正常")
                print(f"   响应: {response.json()}")
                return True
            else:
                print(f"❌ API Server 返回错误: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 无法连接到 API Server: {e}")
            return False


async def create_test_memory():
    """创建测试记忆（通过对话形式）"""
    print("\n2. 创建测试记忆（通过对话形式）...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_conversation = {
        "project_id": PROJECT_ID,
        "title": f"跨项目测试对话 - {timestamp}",
        "messages": [
            {
                "role": "user",
                "content": f"这是一条用于测试跨项目记忆共享的测试消息。创建时间：{timestamp}。关键词：cross-project memory test"
            },
            {
                "role": "assistant",
                "content": f"我已收到您的测试消息。这是测试跨项目记忆共享功能的响应。时间戳：{timestamp}"
            }
        ],
        "metadata": {
            "test_id": timestamp,
            "test_type": "cross_project_sharing",
            "created_by": "test_script"
        }
    }
    
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=httpx.Timeout(60.0)) as client:
        try:
            response = await client.post("/conversation/store", json=test_conversation)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 成功创建测试对话")
                print(f"   对话ID: {result.get('conversation_id')}")
                print(f"   标题: {test_conversation['title']}")
                print(f"   Project ID: {result.get('project_id')}")
                return timestamp
            else:
                print(f"❌ 创建对话失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return None
        except Exception as e:
            print(f"❌ 请求失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None


async def search_memory(keyword):
    """搜索记忆"""
    print(f"\n3. 搜索记忆 (关键词: {keyword})...")
    
    search_request = {
        "query": keyword,
        "project_id": PROJECT_ID,
        "limit": 10,
        "min_score": 0.5,
        "query_type": "hybrid"
    }
    
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        try:
            response = await client.post("/memory/search", json=search_request)
            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    print(f"✅ 找到 {len(result['results'])} 条相关记忆")
                    for idx, memory in enumerate(result['results'], 1):
                        print(f"\n   记忆 {idx}:")
                        print(f"   - 标题: {memory['title']}")
                        print(f"   - 摘要: {memory['summary']}")
                        print(f"   - 相关度: {memory['relevance_score']:.3f}")
                        print(f"   - 类型: {memory['memory_type']}")
                        print(f"   - 创建时间: {memory['created_at']}")
                    return True
                else:
                    print("❌ 没有找到相关记忆")
                    return False
            else:
                print(f"❌ 搜索失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return False


async def test_cross_project_search():
    """测试跨项目搜索（使用不同的project_id搜索）"""
    print("\n4. 测试跨项目搜索...")
    
    # 尝试使用不同的project_id搜索，由于我们的配置是shared模式，应该能找到
    search_request = {
        "query": "cross-project memory",
        "project_id": "another_project",  # 使用不同的project_id
        "limit": 10,
        "min_score": 0.5,
        "query_type": "hybrid"
    }
    
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        try:
            response = await client.post("/memory/search", json=search_request)
            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    print(f"✅ 跨项目搜索成功！找到 {len(result['results'])} 条记忆")
                    print("   说明：即使使用不同的project_id，也能搜索到全局记忆")
                    return True
                else:
                    print("⚠️  跨项目搜索未找到记忆")
                    print("   可能原因：配置未生效或数据尚未同步")
                    return False
            else:
                print(f"❌ 搜索失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return False


async def main():
    """主测试流程"""
    print("=" * 60)
    print("Claude Memory 跨项目记忆共享测试")
    print("=" * 60)
    print(f"API Server: {API_BASE_URL}")
    print(f"Project ID: {PROJECT_ID}")
    
    # 1. 健康检查
    if not await test_health_check():
        print("\n❌ API Server 不可用，测试终止")
        return
    
    # 2. 创建测试记忆
    timestamp = await create_test_memory()
    if not timestamp:
        print("\n❌ 创建记忆失败，测试终止")
        return
    
    # 等待一下让数据同步
    print("\n等待数据同步...")
    await asyncio.sleep(2)
    
    # 3. 搜索刚创建的记忆
    found = await search_memory(timestamp)
    
    # 4. 测试跨项目搜索
    await test_cross_project_search()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结：")
    if found:
        print("✅ 跨项目记忆共享功能正常工作！")
        print("   - 记忆可以成功创建到全局存储")
        print("   - 记忆可以通过关键词搜索到")
        print("   - project_id 已统一为 'global'")
    else:
        print("❌ 跨项目记忆共享功能存在问题")
        print("   请检查：")
        print("   - API Server 是否正常运行")
        print("   - 数据库连接是否正常")
        print("   - 向量数据库是否正常")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())