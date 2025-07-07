"""
Claude记忆管理MCP服务 - 配置模块

提供统一的配置管理功能。
"""

from claude_memory.config.settings import get_settings, Settings

__all__ = ["get_settings", "Settings"]