#!/usr/bin/env python3
"""
配置管理 - 使用pydantic校验
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

class MCPConfig(BaseSettings):
    """MCP服务配置"""
    
    # 基础配置
    service_name: str = Field(default="claude-memory-mcp", description="服务名称")
    log_level: str = Field(default="INFO", description="日志级别")
    
    # 数据库配置
    database_url: Optional[str] = Field(default=None, description="数据库连接URL")
    
    # Qdrant配置
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant URL")
    qdrant_api_key: Optional[str] = Field(default="", description="Qdrant API密钥")
    
    # AI模型API配置
    gemini_api_key: Optional[str] = Field(default=None, description="Gemini API密钥")
    siliconflow_api_key: Optional[str] = Field(default=None, description="SiliconFlow API密钥") 
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API密钥")
    
    # 性能配置
    max_memory_units: int = Field(default=10000, description="最大记忆单元数")
    token_budget_limit: int = Field(default=6000, description="Token预算限制")
    
    # 健康检查配置
    health_check_interval: int = Field(default=60, description="健康检查间隔(秒)")
    ping_timeout: int = Field(default=30, description="心跳超时(秒)")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @field_validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'日志级别必须是: {valid_levels}')
        return v.upper()
    
    @field_validator('qdrant_url')
    def validate_qdrant_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Qdrant URL必须以http://或https://开头')
        return v
    
    def validate_required_for_production(self):
        """生产环境必需配置校验"""
        missing = []
        
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        
        if not self.database_url:
            missing.append("DATABASE_URL")
        
        if missing:
            raise ValueError(f"生产环境缺少必需配置: {', '.join(missing)}")

def load_config() -> MCPConfig:
    """加载配置"""
    return MCPConfig()

def create_sample_env():
    """创建示例.env文件"""
    sample_content = """# Claude Memory MCP 服务配置

# 基础配置
SERVICE_NAME=claude-memory-mcp
LOG_LEVEL=INFO

# 数据库配置 (生产环境必需)
# DATABASE_URL=postgresql://user:pass@localhost:5432/claude_memory

# Qdrant向量数据库
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# AI模型API密钥 (至少需要Gemini)
# GEMINI_API_KEY=your_gemini_key_here
# SILICONFLOW_API_KEY=your_siliconflow_key_here
# OPENROUTER_API_KEY=your_openrouter_key_here

# 性能配置
MAX_MEMORY_UNITS=10000
TOKEN_BUDGET_LIMIT=6000

# 健康检查
HEALTH_CHECK_INTERVAL=60
PING_TIMEOUT=30
"""
    
    env_path = Path(".env.example")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(sample_content)
    
    print(f"✅ 已创建示例配置文件: {env_path}")
    print("📝 请复制为.env并填写必要的API密钥")

if __name__ == "__main__":
    create_sample_env()