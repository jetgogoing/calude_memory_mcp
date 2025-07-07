"""
MemoryFuser模块测试
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from src.claude_memory.fusers.memory_fuser import (
    FusedMemory,
    FusionConfig,
    MemoryFuser
)
from src.claude_memory.models.data_models import MemoryUnit
from src.claude_memory.utils.model_manager import ModelManager
from src.claude_memory.utils.cost_tracker import CostTracker


@pytest.fixture
def fusion_config():
    """创建测试配置"""
    return FusionConfig(
        enabled=True,
        model="gemini-2.5-flash",
        temperature=0.2,
        prompt_template_path="./prompts/test_template.txt",
        token_limit=800,
        language="zh",
        cache_enabled=True,
        cache_ttl_seconds=3600
    )


@pytest.fixture
def mock_model_manager():
    """创建模拟的模型管理器"""
    manager = Mock(spec=ModelManager)
    manager.generate_completion = AsyncMock(return_value={
        "content": "## 项目概况\n- 测试项目\n\n## 关键决策\n1. 使用v1.3架构",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50
        }
    })
    return manager


@pytest.fixture
def sample_memory_units():
    """创建示例记忆单元"""
    return [
        MemoryUnit(
            memory_id="mem_001",
            conversation_id="conv_001",
            timestamp=datetime.now(),
            content="实现了MemoryFuser模块",
            unit_type="decision",
            relevance_score=0.9,
            metadata={"importance": "high"}
        ),
        MemoryUnit(
            memory_id="mem_002",
            conversation_id="conv_001",
            timestamp=datetime.now(),
            content="发现token计算错误",
            unit_type="error_log",
            relevance_score=0.8,
            metadata={"severity": "medium"}
        ),
        MemoryUnit(
            memory_id="mem_003",
            conversation_id="conv_002",
            timestamp=datetime.now(),
            content="def process_memory(data): return data",
            unit_type="code_snippet",
            relevance_score=0.7,
            metadata={"language": "python"}
        )
    ]


class TestFusionConfig:
    """测试融合配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = FusionConfig()
        assert config.enabled is True
        assert config.model == "gemini-2.5-flash"
        assert config.temperature == 0.2
        assert config.token_limit == 800
        assert config.language == "zh"
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = FusionConfig(
            enabled=False,
            model="deepseek-v3",
            temperature=0.5,
            token_limit=1000,
            language="en"
        )
        assert config.enabled is False
        assert config.model == "deepseek-v3"
        assert config.temperature == 0.5
        assert config.token_limit == 1000
        assert config.language == "en"
    
    def test_invalid_temperature(self):
        """测试无效温度值"""
        with pytest.raises(ValidationError):
            FusionConfig(temperature=2.0)  # 超出范围


class TestMemoryFuser:
    """测试MemoryFuser类"""
    
    def test_initialization(self, fusion_config, mock_model_manager):
        """测试初始化"""
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        assert fuser.config == fusion_config
        assert fuser.model_manager == mock_model_manager
        assert isinstance(fuser.cost_tracker, CostTracker)
        assert len(fuser._cache) == 0
    
    def test_load_default_template(self, fusion_config, mock_model_manager):
        """测试加载默认模板"""
        # 使用不存在的模板路径
        fusion_config.prompt_template_path = "/nonexistent/template.txt"
        
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        assert fuser._prompt_template is not None
        assert "Memory Fusion Assistant" in fuser._prompt_template
    
    @pytest.mark.asyncio
    async def test_fuse_memories_disabled(
        self,
        fusion_config,
        mock_model_manager,
        sample_memory_units
    ):
        """测试禁用融合时的行为"""
        fusion_config.enabled = False
        
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        result = await fuser.fuse_memories(
            sample_memory_units,
            "测试查询"
        )
        
        assert isinstance(result, FusedMemory)
        assert result.fusion_model == "none"
        assert result.fusion_cost == 0.0
        assert len(result.source_units) == 3
        # 验证简单拼接
        assert "实现了MemoryFuser模块" in result.content
        assert "发现token计算错误" in result.content
    
    @pytest.mark.asyncio
    async def test_fuse_memories_enabled(
        self,
        fusion_config,
        mock_model_manager,
        sample_memory_units
    ):
        """测试启用融合时的行为"""
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        result = await fuser.fuse_memories(
            sample_memory_units,
            "如何处理记忆？"
        )
        
        assert isinstance(result, FusedMemory)
        assert result.fusion_model == "gemini-2.5-flash"
        assert result.fusion_cost > 0
        assert "项目概况" in result.content
        assert "关键决策" in result.content
        
        # 验证模型调用
        mock_model_manager.generate_completion.assert_called_once()
        call_args = mock_model_manager.generate_completion.call_args
        assert call_args[1]["model"] == "gemini-2.5-flash"
        assert call_args[1]["temperature"] == 0.2
    
    @pytest.mark.asyncio
    async def test_cache_functionality(
        self,
        fusion_config,
        mock_model_manager,
        sample_memory_units
    ):
        """测试缓存功能"""
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        # 第一次调用
        result1 = await fuser.fuse_memories(
            sample_memory_units,
            "测试查询"
        )
        
        # 第二次调用相同参数
        result2 = await fuser.fuse_memories(
            sample_memory_units,
            "测试查询"
        )
        
        # 应该返回相同结果
        assert result1.content == result2.content
        # 模型应该只调用一次
        assert mock_model_manager.generate_completion.call_count == 1
    
    @pytest.mark.asyncio
    async def test_fusion_error_handling(
        self,
        fusion_config,
        mock_model_manager,
        sample_memory_units
    ):
        """测试融合错误处理"""
        # 模拟模型调用失败
        mock_model_manager.generate_completion.side_effect = Exception("API错误")
        
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        result = await fuser.fuse_memories(
            sample_memory_units,
            "测试查询"
        )
        
        # 应该降级到简单拼接
        assert result.fusion_model == "none"
        assert result.fusion_cost == 0.0
        assert "实现了MemoryFuser模块" in result.content
    
    def test_prepare_fragments(
        self,
        fusion_config,
        mock_model_manager,
        sample_memory_units
    ):
        """测试片段准备"""
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        fragments = fuser._prepare_fragments(sample_memory_units)
        
        assert "<fragment_00>" in fragments
        assert "<fragment_01>" in fragments
        assert "<fragment_02>" in fragments
        assert "Type: decision" in fragments
        assert "Type: error_log" in fragments
        assert "Type: code_snippet" in fragments
    
    def test_cache_key_generation(
        self,
        fusion_config,
        mock_model_manager,
        sample_memory_units
    ):
        """测试缓存键生成"""
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        key1 = fuser._generate_cache_key(sample_memory_units, "查询1")
        key2 = fuser._generate_cache_key(sample_memory_units, "查询2")
        key3 = fuser._generate_cache_key(sample_memory_units[:2], "查询1")
        
        # 不同查询应该有不同的键
        assert key1 != key2
        # 不同记忆单元应该有不同的键
        assert key1 != key3
        # 相同输入应该有相同的键
        key4 = fuser._generate_cache_key(sample_memory_units, "查询1")
        assert key1 == key4
    
    @pytest.mark.asyncio
    async def test_batch_fuse(
        self,
        fusion_config,
        mock_model_manager,
        sample_memory_units
    ):
        """测试批量融合"""
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        memory_groups = [
            (sample_memory_units[:2], "查询1"),
            (sample_memory_units[1:], "查询2"),
            (sample_memory_units, "查询3")
        ]
        
        results = await fuser.batch_fuse(memory_groups)
        
        assert len(results) == 3
        assert all(isinstance(r, FusedMemory) for r in results)
        assert mock_model_manager.generate_completion.call_count == 3
    
    @pytest.mark.asyncio
    async def test_batch_fuse_with_error(
        self,
        fusion_config,
        mock_model_manager,
        sample_memory_units
    ):
        """测试批量融合错误处理"""
        # 第二次调用失败
        mock_model_manager.generate_completion.side_effect = [
            {
                "content": "成功融合1",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50}
            },
            Exception("API错误"),
            {
                "content": "成功融合3",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50}
            }
        ]
        
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        memory_groups = [
            (sample_memory_units[:2], "查询1"),
            (sample_memory_units[1:], "查询2"),
            (sample_memory_units, "查询3")
        ]
        
        results = await fuser.batch_fuse(memory_groups)
        
        assert len(results) == 3
        assert "成功融合1" in results[0].content
        assert results[1].fusion_model == "none"  # 降级处理
        assert "成功融合3" in results[2].content
    
    def test_clear_cache(
        self,
        fusion_config,
        mock_model_manager
    ):
        """测试清空缓存"""
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        # 添加一些缓存
        fuser._cache["key1"] = Mock()
        fuser._cache["key2"] = Mock()
        
        assert len(fuser._cache) == 2
        
        fuser.clear_cache()
        
        assert len(fuser._cache) == 0
    
    def test_get_stats(
        self,
        fusion_config,
        mock_model_manager
    ):
        """测试获取统计信息"""
        fuser = MemoryFuser(
            config=fusion_config,
            model_manager=mock_model_manager
        )
        
        # 添加一些缓存
        fuser._cache["key1"] = Mock()
        
        stats = fuser.get_stats()
        
        assert stats["cache_size"] == 1
        assert stats["model"] == "gemini-2.5-flash"
        assert stats["enabled"] is True
        assert "total_cost" in stats