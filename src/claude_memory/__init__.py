"""
Claude记忆管理MCP服务

为Claude CLI提供长期记忆和智能上下文注入能力的独立MCP服务。

核心功能:
- 自动对话采集与解析
- 智能语义压缩与记忆单元生成
- 高性能向量语义检索
- 动态上下文构建与注入
- 多模型协作与成本控制
"""

__version__ = "1.0.0"
__title__ = "Claude记忆管理MCP服务"
__description__ = "为Claude CLI提供长期记忆和智能上下文注入能力的独立MCP服务"
__author__ = "Claude Memory Team"
__license__ = "MIT"

# 延迟导入核心组件，避免在包初始化时导入所有依赖
__all__ = [
    "ConversationCollector",
    "SemanticCompressor", 
    "SemanticRetriever",
    "ContextInjector",
    "ServiceManager",
]

def __getattr__(name):
    """延迟导入模块"""
    if name == "ConversationCollector":
        from claude_memory.collectors.conversation_collector import ConversationCollector
        return ConversationCollector
    elif name == "SemanticCompressor":
        from claude_memory.processors.semantic_compressor import SemanticCompressor
        return SemanticCompressor
    elif name == "SemanticRetriever":
        from claude_memory.retrievers.semantic_retriever import SemanticRetriever
        return SemanticRetriever
    elif name == "ContextInjector":
        from claude_memory.injectors.context_injector import ContextInjector
        return ContextInjector
    elif name == "ServiceManager":
        from claude_memory.managers.service_manager import ServiceManager
        return ServiceManager
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")