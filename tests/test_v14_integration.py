#!/usr/bin/env python3
"""
Claude记忆管理MCP服务 - v1.4集成测试套件

测试v1.4的核心功能：
1. Qwen3-Embedding-8B (4096维)
2. Qwen3-Reranker-8B (Top-20→Top-5)
3. 固定检索策略
4. MemoryFuser环境变量控制
5. 简化的PromptBuilder
"""

import asyncio
import os
import pytest
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_memory.config.settings import get_settings
from claude_memory.models.data_models import MemoryUnit, MemoryUnitType, SearchQuery
from claude_memory.utils.model_manager import ModelManager, EmbeddingResponse, RerankResponse
from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.builders.prompt_builder import PromptBuilder, BuilderConfig
from claude_memory.injectors.context_injector_v13 import ContextInjectorV13, InjectionRequest
from claude_memory.fusers.memory_fuser import MemoryFuser


class TestV14ModelManager:
    """测试v1.4的ModelManager"""
    
    @pytest.fixture
    def model_manager(self):
        """创建ModelManager实例"""
        return ModelManager()
    
    @pytest.mark.asyncio
    async def test_siliconflow_embedding_integration(self, model_manager):
        """测试SiliconFlow嵌入API集成"""
        
        # Mock SiliconFlow API响应
        mock_response = {
            'data': [{'embedding': [0.1] * 4096}],
            'usage': {'prompt_tokens': 10}
        }
        
        with patch.object(model_manager, '_call_siliconflow_embedding') as mock_call:
            mock_call.return_value = EmbeddingResponse(
                embedding=[0.1] * 4096,
                model='qwen3-embedding-8b',
                provider='siliconflow',
                dimension=4096,
                cost_usd=0.001
            )
            
            response = await model_manager.generate_embedding(
                model='qwen3-embedding-8b',
                text='这是一个测试文本'
            )
            
            assert response.dimension == 4096
            assert response.model == 'qwen3-embedding-8b'
            assert response.provider == 'siliconflow'
            assert len(response.embedding) == 4096
    
    @pytest.mark.asyncio
    async def test_siliconflow_rerank_integration(self, model_manager):
        """测试SiliconFlow重排序API集成"""
        
        documents = [
            "这是第一个文档",
            "这是第二个文档",
            "这是第三个文档"
        ]
        
        with patch.object(model_manager, '_call_siliconflow_rerank') as mock_call:
            mock_call.return_value = RerankResponse(
                scores=[0.9, 0.7, 0.5],
                model='qwen3-reranker-8b',
                provider='siliconflow',
                cost_usd=0.002
            )
            
            response = await model_manager.rerank_documents(
                model='qwen3-reranker-8b',
                query='测试查询',
                documents=documents,
                top_k=3
            )
            
            assert len(response.scores) == 3
            assert response.model == 'qwen3-reranker-8b'
            assert response.provider == 'siliconflow'
            assert response.scores[0] > response.scores[1] > response.scores[2]


class TestV14SemanticRetriever:
    """测试v1.4的语义检索器"""
    
    @pytest.fixture
    def mock_db_session(self):
        """模拟数据库会话"""
        return AsyncMock()
    
    @pytest.fixture
    def retriever(self, mock_db_session):
        """创建语义检索器实例"""
        return SemanticRetriever(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_4096_embedding_generation(self, retriever):
        """测试4096维嵌入生成"""
        
        # Mock ModelManager
        with patch('claude_memory.retrievers.semantic_retriever.ModelManager') as MockManager:
            mock_manager = AsyncMock()
            MockManager.return_value = mock_manager
            
            mock_manager.generate_embedding.return_value = EmbeddingResponse(
                embedding=[0.1] * 4096,
                model='qwen3-embedding-8b',
                provider='siliconflow',
                dimension=4096,
                cost_usd=0.001
            )
            
            embedding = await retriever._generate_embedding("测试文本")
            
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (4096,)
            assert embedding.dtype == np.float32
    
    @pytest.mark.asyncio 
    async def test_qwen3_rerank_integration(self, retriever):
        """测试Qwen3重排序集成"""
        
        # 创建模拟搜索结果
        mock_results = []
        for i in range(5):
            memory_unit = MemoryUnit(
                id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                unit_type=MemoryUnitType.GLOBAL,
                summary=f"摘要{i}",
                content=f"内容{i}",
                relevance_score=0.5
            )
            mock_results.append(type('SearchResult', (), {
                'memory_unit': memory_unit,
                'relevance_score': 0.5,
                'rerank_score': None,
                'metadata': {}
            })())
        
        mock_query = SearchQuery(query="测试查询")
        
        # Mock ModelManager
        with patch('claude_memory.retrievers.semantic_retriever.ModelManager') as MockManager:
            mock_manager = AsyncMock()
            MockManager.return_value = mock_manager
            
            mock_manager.rerank_documents.return_value = RerankResponse(
                scores=[0.9, 0.8, 0.7, 0.6, 0.5],
                model='qwen3-reranker-8b',
                provider='siliconflow',
                cost_usd=0.002
            )
            
            reranked = await retriever._rerank_results(mock_results, mock_query)
            
            assert len(reranked) <= 5  # Top-5
            assert reranked[0].rerank_score == 0.9
            assert reranked[1].rerank_score == 0.8
            # 验证按分数降序排列
            for i in range(len(reranked) - 1):
                assert reranked[i].rerank_score >= reranked[i + 1].rerank_score


class TestV14PromptBuilder:
    """测试v1.4的简化PromptBuilder"""
    
    @pytest.fixture
    def builder_config(self):
        """创建构建器配置"""
        return BuilderConfig()
    
    @pytest.fixture
    def prompt_builder(self, builder_config):
        """创建提示构建器"""
        return PromptBuilder(builder_config)
    
    def test_quick_mu_removed_from_priority_weights(self, builder_config):
        """测试Quick-MU已从优先级权重中移除"""
        assert "quick_mu" not in builder_config.priority_weights
        assert "global_mu" in builder_config.priority_weights
        assert "conversation" in builder_config.priority_weights
        assert "archive" in builder_config.priority_weights
    
    def test_quick_mu_removed_from_type_headers(self, prompt_builder):
        """测试Quick-MU已从类型标题中移除"""
        headers = {
            "global_mu": prompt_builder._get_type_header("global_mu"),
            "conversation": prompt_builder._get_type_header("conversation"),
            "archive": prompt_builder._get_type_header("archive")
        }
        
        assert headers["global_mu"] == "全局记忆摘要"
        assert headers["conversation"] == "对话历史" 
        assert headers["archive"] == "归档记忆"
        
        # Quick-MU应该回退到默认格式化
        quick_mu_header = prompt_builder._get_type_header("quick_mu")
        assert quick_mu_header == "Quick Mu"  # 默认title()格式化
    
    def test_simplified_memory_unit_processing(self, prompt_builder):
        """测试简化的记忆单元处理"""
        
        # 创建测试记忆单元（不包含quick_mu）
        memory_units = []
        for unit_type in ["global_mu", "conversation", "archive"]:
            unit = MemoryUnit(
                id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                unit_type=unit_type,
                summary="测试摘要",
                content="测试内容",
                relevance_score=0.8,
                timestamp=datetime.utcnow()
            )
            memory_units.append(unit)
        
        built_prompt = prompt_builder.build(
            memory_units=memory_units,
            query="测试查询",
            max_tokens=1000
        )
        
        assert built_prompt.fragment_count == 3
        assert "全局记忆摘要" in built_prompt.content
        assert "对话历史" in built_prompt.content
        assert "归档记忆" in built_prompt.content


class TestV14ContextInjector:
    """测试v1.4的上下文注入器"""
    
    @pytest.fixture
    def mock_retriever(self):
        """模拟检索器"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_model_manager(self):
        """模拟模型管理器"""
        return AsyncMock()
    
    @pytest.fixture
    def context_injector(self, mock_retriever, mock_model_manager):
        """创建上下文注入器"""
        injector = ContextInjectorV13(mock_retriever, mock_model_manager)
        # Mock settings for fuser_enabled
        injector.settings.memory.fuser_enabled = True
        return injector
    
    @pytest.mark.asyncio
    async def test_fixed_top20_top5_strategy(self, context_injector, mock_retriever):
        """测试固定的Top-20→Top-5策略"""
        
        # Mock search results
        mock_search_results = []
        for i in range(5):  # 模拟rerank后返回5个结果
            mock_search_results.append(type('SearchResult', (), {
                'memory_unit': MemoryUnit(
                    id=uuid.uuid4(),
                    conversation_id=uuid.uuid4(),
                    unit_type=MemoryUnitType.GLOBAL,
                    summary=f"摘要{i}",
                    content=f"内容{i}",
                    relevance_score=0.8 - i * 0.1
                )
            })())
        
        mock_retriever.search.return_value = mock_search_results
        
        memories = await context_injector._retrieve_memories(
            query="测试查询",
            conversation_id="test-conv-id",
            strategy="balanced"  # 策略参数已被忽略
        )
        
        # 验证调用参数
        mock_retriever.search.assert_called_once()
        call_args = mock_retriever.search.call_args
        assert call_args[1]['top_k'] == 20  # 固定Top-20
        
        # 验证返回结果
        assert len(memories) == 5  # rerank后的Top-5
    
    def test_env_controlled_fuser(self, context_injector):
        """测试环境变量控制的MemoryFuser"""
        
        # 测试默认启用
        request = InjectionRequest(
            query="测试查询",
            conversation_id="test-conv-id"
        )
        
        # 创建空的记忆单元列表
        memory_units = []
        
        # 测试fuser启用
        context_injector.settings.memory.fuser_enabled = True
        assert context_injector._should_fuse(request, memory_units) == True
        
        # 测试fuser禁用
        context_injector.settings.memory.fuser_enabled = False
        assert context_injector._should_fuse(request, memory_units) == False
    
    def test_simplified_priority_level(self, context_injector):
        """测试简化的优先级策略"""
        
        # 无论传入什么策略，都应该返回MEDIUM
        strategies = ["minimal", "balanced", "comprehensive", "unknown"]
        
        for strategy in strategies:
            priority = context_injector._get_priority_level(strategy)
            assert priority.value == "medium"


class TestV14EndToEndWorkflow:
    """测试v1.4端到端工作流"""
    
    @pytest.mark.asyncio
    async def test_complete_injection_workflow(self):
        """测试完整的注入工作流：检索→重排→融合→构建→限制→注入"""
        
        # 这是一个集成测试，验证所有组件协同工作
        # 由于涉及多个组件，这里提供测试框架
        
        # TODO: 实现完整的端到端测试
        # 1. 创建测试数据
        # 2. Mock所有外部依赖 
        # 3. 验证整个工作流
        
        assert True  # 占位符，待实现
    
    @pytest.mark.asyncio
    async def test_migration_compatibility(self):
        """测试迁移兼容性"""
        
        # 验证v1.4能正确处理迁移后的数据
        # TODO: 实现迁移兼容性测试
        
        assert True  # 占位符，待实现


class TestV14Configuration:
    """测试v1.4配置系统"""
    
    def test_default_settings_v14(self):
        """测试v1.4默认配置"""
        settings = get_settings()
        
        # 验证Qdrant配置
        assert settings.qdrant.collection_name == "claude_memory_vectors_v14"
        assert settings.qdrant.vector_size == 4096
        
        # 验证模型配置
        assert settings.models.default_embedding_model == "qwen3-embedding-8b"
        assert settings.models.default_rerank_model == "qwen3-reranker-8b"
        
        # 验证检索配置
        assert settings.memory.retrieval_top_k == 20
        assert settings.memory.rerank_top_k == 5
        
        # 验证MemoryFuser默认启用
        assert settings.memory.fuser_enabled == True
    
    def test_env_variable_support(self):
        """测试环境变量支持"""
        
        # 测试关键环境变量的支持
        test_env_vars = {
            'SILICONFLOW_API_KEY': 'test-key',
            'MEMORY_FUSER_ENABLED': 'false',
            'QDRANT_COLLECTION_NAME': 'test-collection',
            'QDRANT_VECTOR_SIZE': '2048'
        }
        
        with patch.dict(os.environ, test_env_vars):
            # 重新加载设置以应用环境变量
            # 注意：实际实现可能需要清除缓存
            pass  # TODO: 实现环境变量测试


@pytest.mark.integration
class TestV14QualityValidation:
    """v1.4质量验证测试"""
    
    def test_golden_standard_dataset(self):
        """使用黄金标准数据集验证v1.4效果"""
        
        # 定义标准查询和期望结果
        golden_test_cases = [
            {
                'query': '如何实现Claude记忆管理',
                'expected_keywords': ['claude', '记忆', '管理', '实现'],
                'min_relevance': 0.8
            },
            {
                'query': '向量数据库配置优化',
                'expected_keywords': ['向量', '数据库', '配置', '优化'],
                'min_relevance': 0.7
            }
        ]
        
        # TODO: 实现质量验证逻辑
        for test_case in golden_test_cases:
            # 1. 执行检索
            # 2. 验证结果质量
            # 3. 与v1.3对比
            pass
    
    def test_performance_benchmarks(self):
        """性能基准测试"""
        
        # 定义性能目标
        performance_targets = {
            'embedding_latency_ms': 150,
            'rerank_latency_ms': 100,
            'end_to_end_latency_ms': 300,
            'memory_usage_mb': 512
        }
        
        # TODO: 实现性能测试
        for metric, target in performance_targets.items():
            # 1. 测量实际性能
            # 2. 与目标对比
            # 3. 记录结果
            pass


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])