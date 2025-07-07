"""
Claude记忆管理MCP服务 - 配置设置

使用Pydantic Settings进行配置管理，支持环境变量和配置文件。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    
    database_url: str = Field(
        default="sqlite:///./data/claude_memory.db",
        description="数据库连接URL"
    )
    pool_size: int = Field(default=10, ge=1, le=50)
    max_overflow: int = Field(default=20, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=1, le=300)
    echo: bool = Field(default=False, description="是否打印SQL语句")


class QdrantSettings(BaseSettings):
    """Qdrant向量数据库配置"""
    
    qdrant_url: str = Field(default="http://localhost:6333")
    api_key: Optional[str] = Field(default=None, alias="qdrant_api_key")
    # v1.4: 新集合名称以支持4096维向量迁移
    collection_name: str = Field(default="claude_memory_vectors_v14")
    # v1.4: 向量维度升级到4096 (Qwen3-Embedding-8B)
    vector_size: int = Field(default=4096, ge=128, le=8192)
    distance_metric: str = Field(default="Cosine", pattern="^(Cosine|Dot|Euclid)$")
    timeout: int = Field(default=30, ge=1, le=300)


class RedisSettings(BaseSettings):
    """Redis缓存配置"""
    
    redis_url: str = Field(default="redis://localhost:6379/0")
    password: Optional[str] = Field(default=None, alias="redis_password")
    max_connections: int = Field(default=10, ge=1, le=100)
    timeout: int = Field(default=5, ge=1, le=60)


class ModelSettings(BaseSettings):
    """AI模型配置"""
    
    # Gemini配置
    gemini_api_key: Optional[str] = Field(default=None)
    gemini_model: str = Field(default="gemini-2.5-pro")
    gemini_embedding_model: str = Field(default="text-embedding-004")
    
    # OpenRouter配置
    openrouter_api_key: Optional[str] = Field(default=None)
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    
    # SiliconFlow配置 (v1.4: Qwen3模型主要提供商)
    siliconflow_api_key: Optional[str] = Field(default=None)
    siliconflow_base_url: str = Field(default="https://api.siliconflow.cn/v1")
    
    # 模型选择策略 (v1.4: 升级为Qwen3系列)
    default_light_model: str = Field(default="deepseek-v3")
    default_heavy_model: str = Field(default="gemini-2.5-pro")
    # v1.4: 默认使用Qwen3-Embedding-8B (4096维)
    default_embedding_model: str = Field(default="Qwen/Qwen3-Embedding-8B")
    # v1.4: 默认使用Qwen3-Reranker-8B
    default_rerank_model: str = Field(default="Qwen/Qwen3-Reranker-8B")
    
    # 超时和重试配置
    request_timeout: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_factor: float = Field(default=2.0, ge=1.0, le=10.0)


class MemorySettings(BaseSettings):
    """记忆系统配置"""
    
    # 记忆模式配置 (v1.3新增)
    default_memory_mode: str = Field(
        default="embedding-only",
        pattern="^(embedding-only|intelligent-compression|hybrid)$",
        description="默认记忆模式"
    )
    
    # 总结策略配置 (v1.3新增)
    summary_manual_trigger_command: str = Field(
        default="/memory review",
        description="手动触发总结命令"
    )
    summary_auto_trigger_keywords: List[str] = Field(
        default_factory=lambda: ["重构", "架构决定", "系统重写"],
        description="自动触发总结的关键词"
    )
    summary_model: str = Field(
        default="gemini-2.5-pro",
        description="总结使用的模型"
    )
    summary_max_tokens: int = Field(default=2048, ge=100, le=8192)
    
    # MemoryFuser配置 (v1.4: 通过环境变量控制)
    fuser_enabled: bool = Field(default=True, description="是否启用记忆融合，可通过MEMORY_FUSER_ENABLED环境变量控制")
    fuser_model: str = Field(default="gemini-2.5-flash", description="融合模型")
    fuser_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    fuser_token_limit: int = Field(default=800, ge=100, le=2000)
    fuser_language: str = Field(default="zh", pattern="^(zh|en)$")
    
    # 记忆单元配置 (v1.4: 移除Quick-MU相关)
    max_memory_units: int = Field(default=10000, ge=100, le=1000000)
    memory_retention_days: int = Field(default=365, ge=1, le=3650)
    # v1.4: 保留用于兼容性
    quick_mu_ttl_hours: int = Field(default=24, ge=1, le=168, description="保留用于兼容性")
    quality_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="记忆质量阈值")
    global_mu_generation_interval_hours: int = Field(default=168, ge=24, le=720)
    
    # Token预算配置
    token_budget_limit: int = Field(default=6000, ge=1000, le=20000)
    max_context_tokens: int = Field(default=4000, ge=500, le=15000)
    emergency_token_limit: int = Field(default=1000, ge=100, le=5000)
    
    # 检索配置 (v1.4: 固定Top-20→Top-5策略)
    retrieval_top_k: int = Field(default=20, ge=1, le=100, description="初始检索数量，固定为20")
    rerank_top_k: int = Field(default=5, ge=1, le=20, description="重排序后返回数量，固定为5")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    hybrid_search_alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    
    @validator('max_context_tokens')
    def validate_context_tokens(cls, v, values):
        if 'token_budget_limit' in values and v >= values['token_budget_limit']:
            raise ValueError('max_context_tokens must be less than token_budget_limit')
        return v


class PerformanceSettings(BaseSettings):
    """性能配置"""
    
    # 并发控制
    max_concurrent_requests: int = Field(default=10, ge=1, le=100)
    request_timeout_seconds: int = Field(default=30, ge=1, le=300)
    batch_size: int = Field(default=50, ge=1, le=1000)
    
    # 缓存配置
    cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    embedding_cache_size: int = Field(default=1000, ge=10, le=10000)
    response_cache_size: int = Field(default=500, ge=10, le=5000)
    
    # 数据库连接池
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: int = Field(default=30, ge=1, le=300)


class MonitoringSettings(BaseSettings):
    """监控配置"""
    
    # Prometheus监控
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090, ge=1024, le=65535)
    
    # 日志配置
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = Field(default="json", pattern="^(json|text)$")
    log_file_path: str = Field(default="./logs/claude_memory.log")
    log_rotation_size: str = Field(default="10MB")
    log_retention_days: int = Field(default=30, ge=1, le=365)
    
    # 告警配置
    alert_email: Optional[str] = Field(default=None)
    alert_webhook_url: Optional[str] = Field(default=None)
    latency_alert_threshold_ms: int = Field(default=500, ge=100, le=5000)
    error_rate_alert_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    
    # 监控间隔配置
    health_check_interval: int = Field(default=60, ge=10, le=600, description="健康检查间隔(秒)")
    metrics_update_interval: int = Field(default=30, ge=5, le=300, description="指标更新间隔(秒)")


class CostSettings(BaseSettings):
    """成本控制配置"""
    
    # API预算配置(USD)
    monthly_budget_usd: float = Field(default=100.0, ge=1.0, le=10000.0)
    daily_budget_usd: float = Field(default=0.5, ge=0.1, le=1000.0)  # v1.3目标: $0.3-0.5/天
    
    # v1.3成本目标
    target_daily_cost_usd: float = Field(default=0.4, ge=0.1, le=1.0)
    embedding_daily_budget_usd: float = Field(default=0.2, ge=0.05, le=0.5)
    fusion_daily_budget_usd: float = Field(default=0.1, ge=0.05, le=0.5)
    compression_daily_budget_usd: float = Field(default=0.1, ge=0.05, le=0.5)
    
    # 预算分配百分比
    gemini_budget_percentage: float = Field(default=30.0, ge=0.0, le=100.0)
    openrouter_budget_percentage: float = Field(default=50.0, ge=0.0, le=100.0)
    siliconflow_budget_percentage: float = Field(default=20.0, ge=0.0, le=100.0)
    
    # 成本控制策略
    enable_cost_alerts: bool = Field(default=True)
    auto_degradation_enabled: bool = Field(default=True)
    cost_alert_threshold: float = Field(default=0.8, ge=0.1, le=1.0)
    
    @validator('siliconflow_budget_percentage')
    def validate_budget_percentages(cls, v, values):
        total = v
        if 'gemini_budget_percentage' in values:
            total += values['gemini_budget_percentage']
        if 'openrouter_budget_percentage' in values:
            total += values['openrouter_budget_percentage']
        
        if total > 100.0:
            raise ValueError('Total budget percentages cannot exceed 100%')
        return v


class CLISettings(BaseSettings):
    """Claude CLI集成配置"""
    
    # CLI捕获配置
    claude_cli_log_path: str = Field(default="~/.claude/logs")
    claude_cli_config_path: str = Field(default="~/.claude/config")
    enable_cli_hooks: bool = Field(default=True)
    cli_polling_interval_seconds: int = Field(default=1, ge=1, le=60)
    
    # 对话过滤配置
    min_conversation_length: int = Field(default=50, ge=10, le=1000)
    max_conversation_length: int = Field(default=50000, ge=1000, le=1000000)
    exclude_system_messages: bool = Field(default=True)
    include_metadata: bool = Field(default=True)


class DevelopmentSettings(BaseSettings):
    """开发配置"""
    
    development_mode: bool = Field(default=False)
    enable_auto_reload: bool = Field(default=False)
    enable_debug_logging: bool = Field(default=False)
    
    # 测试配置
    test_database_url: str = Field(default="sqlite:///./test.db")
    test_qdrant_url: str = Field(default="http://localhost:6333")
    pytest_timeout: int = Field(default=300, ge=60, le=3600)
    
    # Mock配置
    mock_ai_responses: bool = Field(default=False)
    mock_embedding_responses: bool = Field(default=False)


class ServiceSettings(BaseSettings):
    """服务配置"""
    
    version: str = Field(default="1.4.0", description="服务版本")
    name: str = Field(default="Claude记忆管理MCP服务", description="服务名称")
    debug: bool = Field(default=False, description="调试模式")


class Settings(BaseSettings):
    """主配置类"""
    
    # 应用基础配置
    app_name: str = Field(default="Claude记忆管理MCP服务")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1024, le=65535)
    
    # 安全配置
    secret_key: str = Field(default="change-this-in-production")
    api_token: Optional[str] = Field(default=None)
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"]
    )
    
    # 子配置
    service: ServiceSettings = Field(default_factory=ServiceSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    cost: CostSettings = Field(default_factory=CostSettings)
    cli: CLISettings = Field(default_factory=CLISettings)
    dev: DevelopmentSettings = Field(default_factory=DevelopmentSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_nested_delimiter = "__"
        extra = 'allow'  # 允许.env中的额外环境变量
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 确保日志目录存在
        log_dir = Path(self.monitoring.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 确保数据目录存在
        if self.database.database_url.startswith("sqlite"):
            db_path = Path(self.database.database_url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（缓存）"""
    return Settings()


def get_database_url() -> str:
    """获取数据库连接URL"""
    settings = get_settings()
    return settings.database.database_url


def get_test_database_url() -> str:
    """获取测试数据库连接URL"""
    settings = get_settings()
    return settings.dev.test_database_url