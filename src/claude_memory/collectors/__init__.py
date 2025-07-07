"""
Claude记忆管理MCP服务 - 数据采集层

负责从Claude CLI捕获对话数据并进行初步处理。
"""

from claude_memory.collectors.conversation_collector import ConversationCollector

__all__ = ["ConversationCollector"]