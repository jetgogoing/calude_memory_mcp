"""
ContextInjector v1.3 测试
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.claude_memory.injectors.context_injector_v13 import (
    ContextInjectorV13,
    InjectionRequest,
    InjectionResponse,
    InjectionStrategy
)
from src.claude_memory.models.data_models import MemoryUnit, MemoryUnitType
from src.claude_memory.retrievers.semantic_retriever import SemanticRetriever
from src.claude_memory.utils.model_manager import ModelManager
from src.claude_memory.config.settings import Settings


@pytest.fixture
def mock_settings():
    """模拟配置"""
    settings = Mock(spec=Settings)
    settings.memory.default_memory_mode = "embedding-only"
    settings.memory.fuser_enabled = True
    settings.memory.fuser_model = "gemini-2.5-flash"
    settings.memory.fuser_temperature = 0.2
    settings.memory.fuser_token_limit = 800
    settings.memory.fuser_language = "zh"
    settings.memory.token_budget_limit = 6000
    settings.memory.retrieval_top_k = 10
    settings.memory.summary_auto_trigger_keywords = ["重构", "架构决定", "系统重写"]
    settings.memory.summary_model = "gemini-2.5-pro"
    settings.memory.summary_max_tokens = 2048
    settings.cost.daily_budget_usd = 0.5
    return settings


@pytest.fixture
def mock_retriever():
    """模拟检索器"""
    retriever = Mock(spec=SemanticRetriever)
    retriever.search = AsyncMock()
    return retriever


@pytest.fixture
def mock_model_manager():
    """模拟模型管理器"""
    manager = Mock(spec=ModelManager)
    manager.generate_completion = AsyncMock(return_value={
        "content": "融合后的内容",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50
        }
    })
    return manager


@pytest.fixture
def sample_memory_units():
    """示例记忆单元"""
    return [
        MemoryUnit(
            memory_id="mem_001",
            conversation_id="conv_001",
            timestamp=datetime.now(),
            content="实现了v1.3架构",
            unit_type="decision",
            relevance_score=0.9
        ),
        MemoryUnit(
            memory_id="mem_002",
            conversation_id="conv_001",
            timestamp=datetime.now(),
            content="使用embedding-only模式",
            unit_type="conversation",
            relevance_score=0.8
        )
    ]


class TestContextInjectorV13:
    """测试ContextInjector v1.3"""
    
    @pytest.mark.asyncio
    async def test_initialization(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings
    ):
        """测试初始化"""
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            assert injector.retriever == mock_retriever
            assert injector.model_manager == mock_model_manager
            assert injector.fuser is not None
            assert injector.builder is not None
            assert injector.limiter is not None
    
    @pytest.mark.asyncio
    async def test_inject_context_with_fusion(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings,
        sample_memory_units
    ):
        """测试带融合的上下文注入"""
        # 模拟检索结果
        mock_search_results = [
            Mock(memory_unit=unit) for unit in sample_memory_units
        ]
        mock_retriever.search.return_value = mock_search_results
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            request = InjectionRequest(
                query="如何实现v1.3架构？",
                conversation_id="conv_001",
                strategy=InjectionStrategy.BALANCED,
                include_fused=True
            )
            
            response = await injector.inject_context(request)
            
            assert isinstance(response, InjectionResponse)
            assert response.memory_count == 2
            assert response.fused is True
            assert response.token_count > 0
            assert response.cost > 0
            
            # 验证检索器调用
            mock_retriever.search.assert_called_once()
            # 验证模型调用（融合）
            mock_model_manager.generate_completion.assert_called()
    
    @pytest.mark.asyncio
    async def test_inject_context_without_fusion(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings,
        sample_memory_units
    ):
        """测试不带融合的上下文注入"""
        # 禁用融合
        mock_settings.memory.fuser_enabled = False
        
        mock_search_results = [
            Mock(memory_unit=unit) for unit in sample_memory_units
        ]
        mock_retriever.search.return_value = mock_search_results
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            request = InjectionRequest(
                query="查询测试",
                conversation_id="conv_001",
                strategy=InjectionStrategy.MINIMAL
            )
            
            response = await injector.inject_context(request)
            
            assert response.fused is False
            assert response.memory_count == 2
            # 不应该调用模型（因为没有融合）
            mock_model_manager.generate_completion.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_keyword_triggered_fusion(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings,
        sample_memory_units
    ):
        """测试关键词触发融合"""
        # 设置为非embedding-only模式
        mock_settings.memory.default_memory_mode = "intelligent-compression"
        
        mock_search_results = [
            Mock(memory_unit=unit) for unit in sample_memory_units
        ]
        mock_retriever.search.return_value = mock_search_results
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            # 使用包含触发关键词的查询
            request = InjectionRequest(
                query="这次重构的架构决定是什么？",
                conversation_id="conv_001",
                strategy=InjectionStrategy.BALANCED
            )
            
            response = await injector.inject_context(request)
            
            # 应该触发融合
            assert response.fused is True
            mock_model_manager.generate_completion.assert_called()
    
    @pytest.mark.asyncio
    async def test_no_memories_found(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings
    ):
        """测试没有找到记忆的情况"""
        mock_retriever.search.return_value = []
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            request = InjectionRequest(
                query="无关查询",
                conversation_id="conv_999"
            )
            
            response = await injector.inject_context(request)
            
            assert response.content == ""
            assert response.token_count == 0
            assert response.memory_count == 0
            assert response.metadata["reason"] == "no_memories_found"
    
    @pytest.mark.asyncio
    async def test_strategy_configurations(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings,
        sample_memory_units
    ):
        """测试不同策略配置"""
        mock_search_results = [
            Mock(memory_unit=unit) for unit in sample_memory_units
        ]
        mock_retriever.search.return_value = mock_search_results
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            strategies = [
                InjectionStrategy.MINIMAL,
                InjectionStrategy.BALANCED,
                InjectionStrategy.COMPREHENSIVE,
                InjectionStrategy.EMBEDDING_ONLY
            ]
            
            for strategy in strategies:
                request = InjectionRequest(
                    query="测试查询",
                    conversation_id="conv_001",
                    strategy=strategy
                )
                
                response = await injector.inject_context(request)
                assert response.metadata["strategy"] == strategy
    
    @pytest.mark.asyncio
    async def test_manual_review(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings,
        sample_memory_units
    ):
        """测试手动回顾功能"""
        mock_search_results = [
            Mock(memory_unit=unit) for unit in sample_memory_units
        ]
        mock_retriever.search.return_value = mock_search_results
        
        # 模拟总结生成
        mock_model_manager.generate_completion.return_value = {
            "content": "这是对话历史的总结...",
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 100
            }
        }
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            result = await injector.handle_manual_review("conv_001")
            
            assert "对话历史回顾" in result
            assert "这是对话历史的总结" in result
            
            # 验证使用了正确的模型
            call_args = mock_model_manager.generate_completion.call_args
            assert call_args[1]["model"] == "gemini-2.5-pro"
    
    @pytest.mark.asyncio
    async def test_injection_stats(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings
    ):
        """测试注入统计信息"""
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            stats = await injector.get_injection_stats()
            
            assert stats["mode"] == "embedding-only"
            assert stats["fuser_enabled"] is True
            assert "fuser_stats" in stats
            assert "total_cost" in stats
            assert "daily_cost_estimate" in stats
    
    @pytest.mark.asyncio
    async def test_token_limit_handling(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings,
        sample_memory_units
    ):
        """测试Token限制处理"""
        # 创建大量记忆单元
        large_memory_units = sample_memory_units * 10
        mock_search_results = [
            Mock(memory_unit=unit) for unit in large_memory_units
        ]
        mock_retriever.search.return_value = mock_search_results
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            request = InjectionRequest(
                query="测试查询",
                conversation_id="conv_001",
                max_tokens=500  # 设置较小的token限制
            )
            
            response = await injector.inject_context(request)
            
            # 应该被限制在500 tokens以内
            assert response.token_count <= 500
            assert response.metadata.get("truncated") or response.metadata.get("compressed")
    
    @pytest.mark.asyncio
    async def test_error_handling(
        self,
        mock_retriever,
        mock_model_manager,
        mock_settings
    ):
        """测试错误处理"""
        # 模拟检索错误
        mock_retriever.search.side_effect = Exception("检索失败")
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings', return_value=mock_settings):
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            request = InjectionRequest(
                query="测试查询",
                conversation_id="conv_001"
            )
            
            with pytest.raises(Exception) as exc_info:
                await injector.inject_context(request)
            
            assert "检索失败" in str(exc_info.value)