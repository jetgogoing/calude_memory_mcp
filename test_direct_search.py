#!/usr/bin/env python3
"""
直接测试搜索功能
"""

import asyncio
import sys
sys.path.insert(0, '/home/jetgogoing/claude_memory/src')

from claude_memory.retrievers.semantic_retriever import SemanticRetriever, RetrievalRequest
from claude_memory.models.data_models import SearchQuery

async def test_direct_search():
    """直接测试搜索功能"""
    
    # 创建语义检索器
    retriever = SemanticRetriever()
    
    try:
        # 初始化集合
        await retriever.initialize_collection()
        
        # 创建搜索查询
        search_query = SearchQuery(
            query="星云智能",
            query_type="hybrid",
            limit=10,
            min_score=0.1,  # 设置很低的阈值
            context=""
        )
        
        # 创建检索请求
        request = RetrievalRequest(
            query=search_query,
            limit=10,
            min_score=0.1,  # 设置很低的阈值
            rerank=True,
            hybrid_search=True
        )
        
        print("=== 直接搜索测试 ===")
        print(f"搜索关键词: {search_query.query}")
        print(f"最小评分: {request.min_score}")
        
        # 执行搜索
        result = await retriever.retrieve_memories(request)
        
        print(f"搜索结果数量: {len(result.results)}")
        print(f"总找到数量: {result.total_found}")
        print(f"搜索时间: {result.search_time_ms}ms")
        
        if result.results:
            print("\n找到的记忆:")
            for i, search_result in enumerate(result.results):
                print(f"{i+1}. {search_result.memory_unit.title}")
                print(f"   评分: {search_result.relevance_score}")
                print(f"   摘要: {search_result.memory_unit.summary[:100]}...")
                print(f"   匹配类型: {search_result.match_type}")
                print(f"   关键词: {search_result.matched_keywords}")
                print()
        else:
            print("未找到任何记忆")
            
            # 尝试更低的阈值
            print("\n=== 尝试更低的阈值 ===")
            request.min_score = 0.0
            result = await retriever.retrieve_memories(request)
            
            print(f"搜索结果数量: {len(result.results)}")
            if result.results:
                print("找到的记忆:")
                for i, search_result in enumerate(result.results):
                    print(f"{i+1}. {search_result.memory_unit.title}")
                    print(f"   评分: {search_result.relevance_score}")
                    print()
        
    except Exception as e:
        print(f"❌ 搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if hasattr(retriever, 'model_manager') and retriever.model_manager:
            await retriever.model_manager.close()

if __name__ == "__main__":
    asyncio.run(test_direct_search())