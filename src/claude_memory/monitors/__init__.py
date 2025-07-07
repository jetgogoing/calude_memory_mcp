"""
Claude记忆管理MCP服务 - 监控模块
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cost_monitor import CostMonitor, CostAlert, CostReport

__all__ = ["CostMonitor", "CostAlert", "CostReport"]


def __getattr__(name: str):
    """延迟导入模块"""
    if name in ["CostMonitor", "CostAlert", "CostReport"]:
        from .cost_monitor import CostMonitor, CostAlert, CostReport
        return locals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")