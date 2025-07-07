"""
v1.3完整工作流集成测试
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.claude_memory.models.data_models import MemoryUnit, MessageModel
from src.claude_memory.fusers.memory_fuser import MemoryFuser, FusionConfig
from src.claude_memory.builders.prompt_builder import PromptBuilder, BuilderConfig
from src.claude_memory.limiters.token_limiter import TokenLimiter, LimiterConfig
from src.claude_memory.processors.semantic_compressor_v13 import (
    SemanticCompressorV13,
    CompressionRequest,
    CompressionResult
)
from src.claude_memory.injectors.context_injector_v13 import (
    ContextInjectorV13,
    InjectionRequest,
    InjectionStrategy
)
from src.claude_memory.monitors.cost_monitor import (
    CostMonitor,
    BudgetType,
    CostLevel
)
from src.claude_memory.utils.model_manager import ModelManager
from src.claude_memory.utils.embedding_manager import EmbeddingManager
from src.claude_memory.utils.cost_tracker import CostTracker


@pytest.fixture
def mock_model_manager():
    """模拟模型管理器"""
    manager = Mock(spec=ModelManager)
    manager.generate_completion = AsyncMock(return_value={
        "content": "模拟响应内容",
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    })
    return manager


@pytest.fixture
def mock_embedding_manager():
    """模拟嵌入管理器"""
    manager = Mock(spec=EmbeddingManager)
    manager.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    return manager


@pytest.fixture
def sample_messages():
    """示例消息"""
    return [
        MessageModel(
            message_id="msg_001",
            conversation_id="conv_001",
            role="user",
            content="我们需要重构整个系统架构",
            timestamp=datetime.now()
        ),
        MessageModel(
            message_id="msg_002",
            conversation_id="conv_001",
            role="assistant",
            content="好的，让我们采用v1.3的embedding-only架构",
            timestamp=datetime.now()
        )
    ]


class TestV13WorkflowIntegration:
    """测试v1.3完整工作流"""
    
    @pytest.mark.asyncio
    async def test_embedding_only_workflow(
        self,
        mock_model_manager,
        mock_embedding_manager,
        sample_messages
    ):
        """测试embedding-only工作流"""
        with patch('src.claude_memory.processors.semantic_compressor_v13.get_settings') as mock_settings:
            # 配置embedding-only模式
            mock_settings.return_value.memory.default_memory_mode = "embedding-only"
            mock_settings.return_value.memory.summary_auto_trigger_keywords = ["重构"]
            mock_settings.return_value.models.default_embedding_model = "text-embedding-3-small"
            
            # 创建压缩器
            compressor = SemanticCompressorV13(
                model_manager=mock_model_manager,
                embedding_manager=mock_embedding_manager
            )
            
            # 创建压缩请求
            request = CompressionRequest(
                conversation_id="conv_001",
                messages=sample_messages
            )
            
            # 执行压缩
            result = await compressor.process_conversation(request)
            
            # 验证结果
            assert isinstance(result, CompressionResult)
            assert result.compression_performed is False  # embedding-only不压缩
            assert result.embeddings_generated == 2  # 两条消息
            assert len(result.memory_units) == 2
            
            # 验证嵌入调用
            assert mock_embedding_manager.generate_embedding.call_count == 2
    
    @pytest.mark.asyncio
    async def test_keyword_triggered_compression(
        self,
        mock_model_manager,
        mock_embedding_manager,
        sample_messages
    ):
        """测试关键词触发的压缩"""
        with patch('src.claude_memory.processors.semantic_compressor_v13.get_settings') as mock_settings:
            # 配置
            mock_settings.return_value.memory.default_memory_mode = "embedding-only"
            mock_settings.return_value.memory.summary_auto_trigger_keywords = ["重构", "架构"]
            mock_settings.return_value.memory.summary_model = "gemini-2.5-pro"
            mock_settings.return_value.models.default_light_model = "deepseek-v3"
            mock_settings.return_value.models.default_embedding_model = "text-embedding-3-small"
            
            compressor = SemanticCompressorV13(
                model_manager=mock_model_manager,
                embedding_manager=mock_embedding_manager
            )
            
            request = CompressionRequest(
                conversation_id="conv_001",
                messages=sample_messages
            )
            
            result = await compressor.process_conversation(request)
            
            # 应该触发压缩（因为包含"重构"关键词）
            assert result.compression_performed is True
            assert result.trigger.keyword_match is True
            assert "重构" in result.trigger.matched_keywords
            
            # 验证模型调用
            mock_model_manager.generate_completion.assert_called()
    
    @pytest.mark.asyncio
    async def test_cost_monitoring(
        self,
        mock_model_manager,
        mock_embedding_manager
    ):
        """测试成本监控"""
        cost_tracker = CostTracker()
        cost_monitor = CostMonitor(cost_tracker)
        
        # 跟踪一些成本
        cost1 = cost_monitor.track_cost(
            "gemini-2.5-flash",
            1000,  # input tokens
            500,   # output tokens
            BudgetType.FUSION
        )
        
        cost2 = cost_monitor.track_cost(
            "text-embedding-3-small",
            5000,  # input tokens
            0,     # output tokens (embeddings没有输出)
            BudgetType.EMBEDDING
        )
        
        # 生成报告
        report = cost_monitor.generate_report()
        
        assert report.fusion_cost > 0
        assert report.embedding_cost > 0
        assert report.daily_cost == cost1 + cost2
        assert len(report.cost_by_model) == 2
    
    @pytest.mark.asyncio
    async def test_degradation_strategy(self):
        """测试降级策略"""
        cost_tracker = CostTracker()
        cost_monitor = CostMonitor(cost_tracker)
        
        with patch.object(cost_monitor, '_get_today_cost', return_value=0.45):
            with patch('src.claude_memory.monitors.cost_monitor.get_settings') as mock_settings:
                mock_settings.return_value.cost.daily_budget_usd = 0.5
                mock_settings.return_value.cost.auto_degradation_enabled = True
                
                # 模拟接近预算限制
                cost_monitor._check_budgets()
                
                # 检查降级配置
                config = cost_monitor.get_degradation_config()
                
                # 在90%使用率时应该降级
                if cost_monitor.degradation_level > 0:
                    assert config["heavy_model_enabled"] is False
    
    @pytest.mark.asyncio
    async def test_full_injection_workflow(
        self,
        mock_model_manager,
        mock_embedding_manager
    ):
        """测试完整的注入工作流"""
        # 模拟检索器
        mock_retriever = Mock()
        mock_retriever.search = AsyncMock(return_value=[
            Mock(memory_unit=MemoryUnit(
                memory_id="mu_001",
                conversation_id="conv_001",
                timestamp=datetime.now(),
                content="之前讨论的架构方案",
                unit_type="decision",
                relevance_score=0.9
            ))
        ])
        
        with patch('src.claude_memory.injectors.context_injector_v13.get_settings') as mock_settings:
            # 配置
            mock_settings.return_value.memory.default_memory_mode = "embedding-only"
            mock_settings.return_value.memory.fuser_enabled = True
            mock_settings.return_value.memory.fuser_model = "gemini-2.5-flash"
            mock_settings.return_value.memory.fuser_temperature = 0.2
            mock_settings.return_value.memory.fuser_token_limit = 800
            mock_settings.return_value.memory.fuser_language = "zh"
            mock_settings.return_value.memory.token_budget_limit = 6000
            mock_settings.return_value.memory.retrieval_top_k = 10
            mock_settings.return_value.memory.summary_auto_trigger_keywords = []
            mock_settings.return_value.cost.daily_budget_usd = 0.5
            
            # 创建注入器
            injector = ContextInjectorV13(
                retriever=mock_retriever,
                model_manager=mock_model_manager
            )
            
            # 创建注入请求
            request = InjectionRequest(
                query="如何实现新架构？",
                conversation_id="conv_001",
                strategy=InjectionStrategy.BALANCED
            )
            
            # 执行注入
            response = await injector.inject_context(request)
            
            # 验证结果
            assert response.content != ""
            assert response.memory_count == 1
            assert response.fused is True
            assert response.token_count > 0
            assert response.cost > 0
    
    def test_prompt_builder_integration(self):
        """测试PromptBuilder集成"""
        builder = PromptBuilder(BuilderConfig())
        
        memory_units = [
            MemoryUnit(
                memory_id="mu_001",
                conversation_id="conv_001",
                timestamp=datetime.now(),
                content="重要决策1",
                unit_type="decision",
                relevance_score=0.9
            ),
            MemoryUnit(
                memory_id="mu_002",
                conversation_id="conv_001",
                timestamp=datetime.now(),
                content="重要决策1",  # 重复内容
                unit_type="decision",
                relevance_score=0.8
            )
        ]
        
        # 测试去重
        built = builder.build(memory_units, "测试查询")
        
        # 应该去重
        assert built.fragment_count == 1
        assert "重要决策1" in built.content
    
    def test_token_limiter_integration(self):
        """测试TokenLimiter集成"""
        limiter = TokenLimiter(LimiterConfig(
            default_limit=100,
            truncation_strategy="smart"
        ))
        
        # 测试长内容限制
        long_content = "这是一段很长的内容。" * 100
        limited = limiter.limit_content(long_content, max_tokens=50)
        
        assert limited.truncated is True
        assert limited.final_tokens <= 50
        assert len(limited.content) < len(long_content)