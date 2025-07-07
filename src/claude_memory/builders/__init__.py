"""
Claude记忆管理MCP服务 - 提示构建模块

提供提示词的智能构建和组织功能。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .prompt_builder import PromptBuilder

__all__ = ["PromptBuilder"]


def __getattr__(name: str):
    """延迟导入模块"""
    if name == "PromptBuilder":
        from .prompt_builder import PromptBuilder
        return PromptBuilder
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")