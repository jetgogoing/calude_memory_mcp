#!/usr/bin/env python3
"""
快速测试Qwen3-Reranker集成是否正常工作
"""

import asyncio
import json
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from claude_memory.config.settings import get_settings
from claude_memory.utils.model_manager import ModelManager


async def test_reranker_api():
    """测试Reranker API调用"""
    print("=== 测试Qwen3-Reranker API ===\n")
    
    settings = get_settings()
    model_manager = ModelManager()
    
    try:
        await model_manager.initialize()
        
        # 测试查询和文档
        query = "如何在Claude Memory系统中实现AI重排序功能"
        documents = [
            "使用Qwen3-Reranker-8B模型进行语义重排序，提高检索精度",
            "系统架构包括MCP Server、API Server和向量数据库",
            "数据库已经简化，删除了项目隔离功能",
            "使用DeepSeek-V2.5进行记忆融合和摘要生成",
            "支持降级策略，当API失败时使用规则算法"
        ]
        
        print(f"查询: {query}")
        print(f"文档数量: {len(documents)}")
        print(f"模型: {settings.models.default_rerank_model}")
        print(f"API Base: {settings.models.siliconflow_base_url}")
        print()
        
        # 调用重排序API
        start_time = datetime.utcnow()
        
        response = await model_manager.rerank_documents(
            model=settings.models.default_rerank_model,
            query=query,
            documents=documents,
            top_k=3
        )
        
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        print("=== 重排序结果 ===")
        print(f"耗时: {elapsed_ms:.2f}ms")
        print(f"返回数量: {len(response.scores)}")
        print(f"模型: {response.model}")
        print(f"提供商: {response.provider}")
        print(f"成本: ${response.cost_usd:.6f}")
        print()
        
        # 显示重排序后的文档
        print("=== 重排序后的文档（按相关性降序）===")
        indexed_scores = [(i, score) for i, score in enumerate(response.scores)]
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        
        for rank, (idx, score) in enumerate(indexed_scores[:3]):
            print(f"{rank+1}. [Score: {score:.4f}] {documents[idx]}")
        
        print("\n✅ Reranker API测试成功！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        
        # 检查常见问题
        if "401" in str(e) or "unauthorized" in str(e).lower():
            print("\n💡 提示: 请检查SILICONFLOW_API_KEY环境变量是否设置正确")
        elif "connection" in str(e).lower():
            print("\n💡 提示: 请检查网络连接或API地址是否正确")
        
    finally:
        await model_manager.close()


async def test_full_retrieval_flow():
    """测试完整的检索流程"""
    print("\n\n=== 测试完整检索流程 ===\n")
    
    from claude_memory.retrievers.semantic_retriever import SemanticRetriever, RetrievalRequest
    from claude_memory.models.data_models import SearchQuery, SearchQueryType
    
    retriever = SemanticRetriever()
    
    try:
        # 初始化集合
        await retriever.initialize_collection()
        
        # 创建测试查询
        query = SearchQuery(
            query="Claude Memory系统的AI重排序实现",
            query_type=SearchQueryType.SEMANTIC
        )
        
        request = RetrievalRequest(
            query=query,
            limit=20,
            rerank=True,
            hybrid_search=True
        )
        
        print(f"查询: {query.query}")
        print(f"初始检索数量: {request.limit}")
        print(f"启用AI重排序: {request.rerank}")
        print(f"使用混合搜索: {request.hybrid_search}")
        print()
        
        # 执行检索
        result = await retriever.retrieve_memories(request)
        
        print("=== 检索结果 ===")
        print(f"总候选数: {result.total_found}")
        print(f"返回结果: {len(result.results)}")
        print(f"检索策略: {result.retrieval_strategy}")
        print(f"检索耗时: {result.search_time_ms:.2f}ms")
        if result.rerank_time_ms:
            print(f"重排序耗时: {result.rerank_time_ms:.2f}ms")
        
        if result.results:
            print("\n前3条结果:")
            for i, res in enumerate(result.results[:3]):
                print(f"{i+1}. {res.memory_unit.title}")
                print(f"   相关性分数: {res.relevance_score:.4f}")
                if hasattr(res, 'rerank_score'):
                    print(f"   重排序分数: {res.rerank_score:.4f}")
                print(f"   匹配类型: {res.match_type}")
        
        print("\n✅ 完整检索流程测试成功！")
        
    except Exception as e:
        print(f"\n❌ 检索测试失败: {str(e)}")
        
    finally:
        await retriever.close()


async def main():
    """主测试函数"""
    print("=" * 60)
    print("Claude Memory - Qwen3-Reranker 集成测试")
    print("=" * 60)
    
    # 检查环境变量
    settings = get_settings()
    if not settings.models.siliconflow_api_key:
        print("\n⚠️  警告: SILICONFLOW_API_KEY 未设置")
        print("请设置环境变量: export SILICONFLOW_API_KEY='your_api_key'")
        return
    
    # 测试Reranker API
    await test_reranker_api()
    
    # 测试完整检索流程
    await test_full_retrieval_flow()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())