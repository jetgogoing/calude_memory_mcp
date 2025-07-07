"""
Claude记忆管理MCP服务 - Token限制模块

提供Token预算控制和智能截断功能。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .token_limiter import TokenLimiter

__all__ = ["TokenLimiter"]


def __getattr__(name: str):
    """延迟导入模块"""
    if name == "TokenLimiter":
        from .token_limiter import TokenLimiter
        return TokenLimiter
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")