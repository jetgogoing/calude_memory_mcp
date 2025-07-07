"""
Claude记忆管理MCP服务 - 记忆融合模块

提供记忆片段的智能融合和结构化整理功能。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_fuser import MemoryFuser

__all__ = ["MemoryFuser"]


def __getattr__(name: str):
    """延迟导入模块"""
    if name == "MemoryFuser":
        from .memory_fuser import MemoryFuser
        return MemoryFuser
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")