"""
Claude记忆管理MCP服务 - 语义处理层

负责对话内容的语义压缩和记忆单元生成。
"""

from claude_memory.processors.semantic_compressor import SemanticCompressor

__all__ = ["SemanticCompressor"]