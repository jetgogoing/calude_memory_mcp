"""
Claude记忆管理MCP服务 - Token限制模块

提供Token预算控制和智能截断功能。
"""

# Token限制模块已删除

__all__ = []


def __getattr__(name: str):
    """已删除所有限制模块"""
    raise AttributeError(f"module '{__name__}' has no attribute '{name}' - all limiters have been removed")