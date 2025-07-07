"""
测试v1.3配置更新
"""

import pytest
from pydantic import ValidationError

from src.claude_memory.config.settings import (
    MemorySettings,
    CostSettings,
    Settings,
    get_settings
)


class TestMemorySettingsV13:
    """测试v1.3记忆配置"""
    
    def test_default_memory_mode(self):
        """测试默认记忆模式"""
        settings = MemorySettings()
        assert settings.default_memory_mode == "embedding-only"
    
    def test_valid_memory_modes(self):
        """测试有效的记忆模式"""
        for mode in ["embedding-only", "intelligent-compression", "hybrid"]:
            settings = MemorySettings(default_memory_mode=mode)
            assert settings.default_memory_mode == mode
    
    def test_invalid_memory_mode(self):
        """测试无效的记忆模式"""
        with pytest.raises(ValidationError):
            MemorySettings(default_memory_mode="invalid-mode")
    
    def test_summary_trigger_config(self):
        """测试总结触发配置"""
        settings = MemorySettings()
        assert settings.summary_manual_trigger_command == "/memory review"
        assert "重构" in settings.summary_auto_trigger_keywords
        assert "架构决定" in settings.summary_auto_trigger_keywords
        assert "系统重写" in settings.summary_auto_trigger_keywords
        assert settings.summary_model == "gemini-2.5-pro"
        assert settings.summary_max_tokens == 2048
    
    def test_fuser_config(self):
        """测试融合器配置"""
        settings = MemorySettings()
        assert settings.fuser_enabled is True
        assert settings.fuser_model == "gemini-2.5-flash"
        assert settings.fuser_temperature == 0.2
        assert settings.fuser_token_limit == 800
        assert settings.fuser_language == "zh"
    
    def test_fuser_language_validation(self):
        """测试融合器语言验证"""
        # 有效语言
        settings_zh = MemorySettings(fuser_language="zh")
        assert settings_zh.fuser_language == "zh"
        
        settings_en = MemorySettings(fuser_language="en")
        assert settings_en.fuser_language == "en"
        
        # 无效语言
        with pytest.raises(ValidationError):
            MemorySettings(fuser_language="jp")
    
    def test_custom_summary_keywords(self):
        """测试自定义总结关键词"""
        custom_keywords = ["紧急修复", "breaking change", "数据迁移"]
        settings = MemorySettings(
            summary_auto_trigger_keywords=custom_keywords
        )
        assert settings.summary_auto_trigger_keywords == custom_keywords


class TestCostSettingsV13:
    """测试v1.3成本配置"""
    
    def test_daily_budget_target(self):
        """测试每日预算目标"""
        settings = CostSettings()
        assert settings.daily_budget_usd == 0.5
        assert settings.target_daily_cost_usd == 0.4
    
    def test_cost_breakdown(self):
        """测试成本分解"""
        settings = CostSettings()
        assert settings.embedding_daily_budget_usd == 0.2
        assert settings.fusion_daily_budget_usd == 0.1
        assert settings.compression_daily_budget_usd == 0.1
        
        # 验证总和接近目标
        total = (
            settings.embedding_daily_budget_usd +
            settings.fusion_daily_budget_usd +
            settings.compression_daily_budget_usd
        )
        assert abs(total - settings.target_daily_cost_usd) < 0.01
    
    def test_custom_cost_targets(self):
        """测试自定义成本目标"""
        settings = CostSettings(
            target_daily_cost_usd=0.3,
            embedding_daily_budget_usd=0.15,
            fusion_daily_budget_usd=0.08,
            compression_daily_budget_usd=0.07
        )
        
        assert settings.target_daily_cost_usd == 0.3
        total = (
            settings.embedding_daily_budget_usd +
            settings.fusion_daily_budget_usd +
            settings.compression_daily_budget_usd
        )
        assert abs(total - 0.3) < 0.01


class TestSettingsIntegrationV13:
    """测试v1.3配置集成"""
    
    def test_settings_includes_v13_config(self):
        """测试主配置包含v1.3设置"""
        settings = Settings()
        
        # 检查记忆设置
        assert hasattr(settings.memory, "default_memory_mode")
        assert hasattr(settings.memory, "fuser_enabled")
        assert hasattr(settings.memory, "summary_auto_trigger_keywords")
        
        # 检查成本设置
        assert hasattr(settings.cost, "target_daily_cost_usd")
        assert hasattr(settings.cost, "embedding_daily_budget_usd")
    
    def test_get_settings_singleton(self):
        """测试配置单例"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # 应该是同一个实例
        assert settings1 is settings2
        
        # 验证v1.3配置存在
        assert settings1.memory.default_memory_mode == "embedding-only"
        assert settings1.cost.daily_budget_usd == 0.5
    
    def test_env_override(self):
        """测试环境变量覆盖"""
        import os
        
        # 设置环境变量
        os.environ["MEMORY__DEFAULT_MEMORY_MODE"] = "hybrid"
        os.environ["MEMORY__FUSER_ENABLED"] = "false"
        os.environ["COST__TARGET_DAILY_COST_USD"] = "0.25"
        
        # 清除缓存以重新加载
        get_settings.cache_clear()
        
        try:
            settings = get_settings()
            assert settings.memory.default_memory_mode == "hybrid"
            assert settings.memory.fuser_enabled is False
            assert settings.cost.target_daily_cost_usd == 0.25
        finally:
            # 清理环境变量
            os.environ.pop("MEMORY__DEFAULT_MEMORY_MODE", None)
            os.environ.pop("MEMORY__FUSER_ENABLED", None)
            os.environ.pop("COST__TARGET_DAILY_COST_USD", None)
            get_settings.cache_clear()