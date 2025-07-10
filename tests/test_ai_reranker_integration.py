"""
Claude记忆管理MCP服务 - AI Reranker集成测试

测试完整的RAG流程：Qdrant召回 → Qwen3-Reranker精排 → DeepSeek融合
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from claude_memory.config.settings import get_settings
from claude_memory.models.data_models import (
    MemoryUnitModel, 
    MemoryUnitType, 
    SearchQuery,
    SearchQueryType
)
from claude_memory.retrievers.semantic_retriever import (
    SemanticRetriever, 
    RetrievalRequest
)
from claude_memory.fusers.memory_fuser import MemoryFuser, FusionConfig
from claude_memory.utils.model_manager import ModelManager


class TestAIRerankerIntegration:
    """AI Reranker集成测试"""
    
    @pytest.fixture
    async def setup(self):
        """测试环境设置"""
        settings = get_settings()
        model_manager = ModelManager()
        
        # 初始化组件
        retriever = SemanticRetriever()
        await retriever.initialize_collection()
        
        fusion_config = FusionConfig(
            enabled=True,
            model=settings.memory.fuser_model,
            temperature=settings.memory.fuser_temperature,
            token_limit=settings.memory.fuser_token_limit
        )
        fuser = MemoryFuser(config=fusion_config, model_manager=model_manager)
        
        yield {
            'settings': settings,
            'retriever': retriever,
            'fuser': fuser,
            'model_manager': model_manager
        }
        
        # 清理
        await retriever.close()
        await model_manager.close()
    
    @pytest.mark.asyncio
    async def test_full_rag_pipeline(self, setup):
        """测试完整的RAG流程"""
        retriever = setup['retriever']
        fuser = setup['fuser']
        settings = setup['settings']
        
        # 1. 创建测试记忆单元
        test_memories = [
            MemoryUnitModel(
                id=str(uuid4()),
                conversation_id=str(uuid4()),
                unit_type=MemoryUnitType.CONVERSATION,
                title="Qwen3-Reranker实现讨论",
                summary="讨论了如何在Claude Memory系统中集成Qwen3-Reranker-8B模型",
                content="用户要求实现完整的RAG流程，包括向量检索、AI重排序和记忆融合。系统需要使用SiliconFlow API调用Qwen3-Reranker-8B进行语义重排序。",
                keywords=["reranker", "qwen3", "rag", "向量检索"],
                token_count=100,
                created_at=datetime.utcnow(),
                metadata={'importance_score': 0.9}
            ),
            MemoryUnitModel(
                id=str(uuid4()),
                conversation_id=str(uuid4()),
                unit_type=MemoryUnitType.DOCUMENTATION,
                title="系统架构文档",
                summary="Claude Memory系统的整体架构设计",
                content="系统采用混合架构，包括MCP Server、API Server和自动收集器。数据存储使用PostgreSQL和Qdrant向量数据库。",
                keywords=["架构", "系统设计", "数据库"],
                token_count=150,
                created_at=datetime.utcnow() - timedelta(days=5),
                metadata={'importance_score': 0.8}
            ),
            MemoryUnitModel(
                id=str(uuid4()),
                conversation_id=str(uuid4()),
                unit_type=MemoryUnitType.CONVERSATION,
                title="数据库简化讨论",
                summary="用户要求删除项目隔离，实现全局记忆共享",
                content="用户对项目隔离功能表示厌恶，要求完全删除projects表，让所有对话记录全局共享。",
                keywords=["数据库", "项目隔离", "全局共享"],
                token_count=80,
                created_at=datetime.utcnow() - timedelta(days=1),
                metadata={'importance_score': 0.7}
            )
        ]
        
        # 存储测试记忆到向量数据库
        for memory in test_memories:
            success = await retriever.store_memory_unit(memory)
            assert success, f"Failed to store memory {memory.id}"
        
        # 2. 执行检索（包含AI重排序）
        query = SearchQuery(
            query="如何实现Qwen3 Reranker集成",
            query_type=SearchQueryType.SEMANTIC
        )
        
        request = RetrievalRequest(
            query=query,
            limit=50,
            min_score=0.2,
            rerank=True,  # 启用AI重排序
            hybrid_search=True
        )
        
        # 执行检索
        retrieval_result = await retriever.retrieve_memories(request)
        
        # 验证检索结果
        assert retrieval_result.total_found > 0, "No memories found"
        assert len(retrieval_result.results) > 0, "No results returned"
        assert retrieval_result.rerank_time_ms is not None, "Rerank time not recorded"
        
        # 检查重排序是否生效
        top_result = retrieval_result.results[0]
        assert hasattr(top_result, 'rerank_score'), "Rerank score not set"
        assert 'rerank_model' in top_result.metadata, "Rerank model not recorded"
        assert top_result.metadata['rerank_model'] == settings.models.default_rerank_model
        
        # 3. 执行记忆融合
        memory_units = [r.memory_unit for r in retrieval_result.results[:5]]
        fused_memory = await fuser.fuse_memories(
            memory_units=memory_units,
            query=query.query,
            max_tokens=800
        )
        
        # 验证融合结果
        assert fused_memory.content, "Fused content is empty"
        assert fused_memory.fusion_model == settings.memory.fuser_model
        assert len(fused_memory.source_units) == len(memory_units)
        
        # 打印测试结果
        print(f"\n=== RAG Pipeline Test Results ===")
        print(f"检索到 {retrieval_result.total_found} 条记忆")
        print(f"AI重排序后返回 {len(retrieval_result.results)} 条")
        print(f"重排序耗时: {retrieval_result.rerank_time_ms:.2f}ms")
        print(f"\n最相关记忆:")
        for i, result in enumerate(retrieval_result.results[:3]):
            print(f"{i+1}. {result.memory_unit.title} (score: {result.relevance_score:.3f})")
        print(f"\n融合后的记忆摘要 ({fused_memory.token_count} tokens):")
        print(fused_memory.content[:500] + "..." if len(fused_memory.content) > 500 else fused_memory.content)
    
    @pytest.mark.asyncio
    async def test_reranker_fallback(self, setup):
        """测试Reranker降级策略"""
        retriever = setup['retriever']
        
        # 临时修改配置，使用无效的API key触发降级
        original_key = setup['settings'].models.siliconflow_api_key
        setup['settings'].models.siliconflow_api_key = "invalid_key"
        
        # 创建测试查询
        query = SearchQuery(
            query="测试降级策略",
            query_type=SearchQueryType.SEMANTIC
        )
        
        request = RetrievalRequest(
            query=query,
            limit=10,
            rerank=True
        )
        
        # 执行检索（应该触发降级）
        retrieval_result = await retriever.retrieve_memories(request)
        
        # 恢复原始配置
        setup['settings'].models.siliconflow_api_key = original_key
        
        # 验证降级是否成功
        assert retrieval_result is not None, "Retrieval failed completely"
        # 降级时不会有rerank_score，但应该有结果
        if retrieval_result.results:
            # 检查是否使用了规则算法
            assert retrieval_result.retrieval_strategy in ['semantic_only', 'hybrid', 'keyword_only']
    
    @pytest.mark.asyncio
    async def test_batch_rerank_performance(self, setup):
        """测试批量重排序性能"""
        model_manager = setup['model_manager']
        
        # 准备批量测试数据
        query = "Claude Memory系统架构优化"
        documents = [
            "系统采用混合架构设计，包括MCP Server和API Server",
            "使用Qdrant向量数据库存储4096维向量",
            "集成Qwen3-Reranker-8B进行语义重排序",
            "支持全局记忆共享，取消项目隔离",
            "使用DeepSeek-V2.5进行记忆融合",
            "PostgreSQL存储结构化数据",
            "实现了自动对话收集功能",
            "支持多种检索策略：语义、关键词、混合",
            "提供降级策略保证系统可用性",
            "监控系统性能和成本指标"
        ]
        
        # 执行批量重排序
        start_time = datetime.utcnow()
        
        rerank_response = await model_manager.rerank_documents(
            model=setup['settings'].models.default_rerank_model,
            query=query,
            documents=documents,
            top_k=5
        )
        
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # 验证结果
        assert len(rerank_response.scores) == 5, "Should return top 5 results"
        assert all(0 <= score <= 1 for score in rerank_response.scores), "Scores should be normalized"
        assert elapsed_ms < 5000, f"Rerank took too long: {elapsed_ms}ms"
        
        print(f"\n=== Batch Rerank Performance ===")
        print(f"文档数量: {len(documents)}")
        print(f"返回Top-K: 5")
        print(f"耗时: {elapsed_ms:.2f}ms")
        print(f"模型: {rerank_response.model}")
        print(f"成本: ${rerank_response.cost_usd:.4f}")


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))