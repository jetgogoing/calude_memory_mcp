"""
Claude记忆管理MCP服务 - MCP服务器实现

提供标准的MCP协议接口，支持与Claude CLI的无缝集成。
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from io import StringIO

import httpx

import structlog
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    ClientCapabilities,
    Implementation,
    Resource,
    ServerCapabilities,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from pydantic import AnyUrl

from claude_memory.config.settings import get_settings
from claude_memory.database.session_manager import get_session_manager
from claude_memory.managers.service_manager import ServiceManager
# from claude_memory.managers.cross_project_search import CrossProjectSearchRequest  # 已删除：全局共享记忆
from claude_memory.models.data_models import (
    ContextInjectionRequest,
    SearchQuery,
    HealthStatus,
)
from claude_memory.utils.error_handling import handle_exceptions

# 配置结构化日志 - 只写入文件，不干扰stdio
import os
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

# 创建日志目录
log_dir = Path(__file__).parent.parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# 配置文件日志handler
file_handler = TimedRotatingFileHandler(
    log_dir / "mcp_server.log",
    when="midnight", interval=1, backupCount=30
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))

# 配置structlog只写文件
logging.getLogger().handlers = [file_handler]
logging.getLogger().setLevel(logging.INFO)

# stderr重定向类，避免干扰stdio通信
class StderrToLogger:
    """将stderr重定向到日志文件，避免干扰stdio通信"""
    
    def __init__(self, logger):
        self.logger = logger
        self.buffer = StringIO()
    
    def write(self, msg):
        if msg.strip():
            self.logger.error(f"STDERR: {msg.strip()}")
    
    def flush(self):
        pass

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class ClaudeMemoryMCPServer:
    """
    Claude记忆管理MCP服务器
    
    实现MCP协议接口，提供以下工具:
    - claude_memory_search: 搜索相关记忆
    - claude_memory_inject: 注入上下文
    - claude_memory_status: 获取服务状态
    - claude_memory_health: 健康检查
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.server = Server("claude-memory-mcp")
        self.service_manager: Optional[ServiceManager] = None
        self.session_manager = None
        
        # API Server 配置
        self.api_base_url = os.getenv("CLAUDE_MEMORY_API_URL", "http://localhost:8000")
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # 注册MCP处理器
        self._register_handlers()

    async def initialize(self) -> None:
        """
        初始化MCP服务器
        """
        try:
            logger.info("Initializing Claude Memory MCP Server...")
            
            # 初始化HTTP客户端
            self.http_client = httpx.AsyncClient(
                base_url=self.api_base_url,
                timeout=httpx.Timeout(30.0),
                headers={"Content-Type": "application/json"}
            )
            
            # 检查API Server健康状态
            try:
                response = await self.http_client.get("/health")
                if response.status_code != 200:
                    logger.warning(f"API Server health check returned {response.status_code}")
            except Exception as e:
                logger.warning(f"Failed to connect to API Server at {self.api_base_url}: {e}")
            
            # 保留原有的ServiceManager初始化作为后备
            try:
                self.session_manager = await get_session_manager()
                self.service_manager = ServiceManager()
                await self.service_manager.start_service()
                logger.info("ServiceManager initialized as fallback")
            except Exception as e:
                logger.warning("Failed to initialize ServiceManager (will use API only)", error=str(e))
            
            logger.info("Claude Memory MCP Server initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize MCP server", error=str(e))
            raise

    async def cleanup(self) -> None:
        """
        清理资源
        """
        try:
            logger.info("Cleaning up Claude Memory MCP Server...")
            
            if self.http_client:
                await self.http_client.aclose()
                self.http_client = None
            
            if self.service_manager:
                await self.service_manager.stop_service()
                self.service_manager = None
            
            if self.session_manager:
                await self.session_manager.close()
                self.session_manager = None
            
            logger.info("Claude Memory MCP Server cleanup completed")
            
        except Exception as e:
            logger.error("Error during cleanup", error=str(e))

    def _register_handlers(self) -> None:
        """
        注册MCP处理器
        """
        # 注册服务器能力
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """列出可用资源"""
            return [
                Resource(
                    uri=AnyUrl("claude://memory/search"),
                    name="记忆搜索",
                    description="搜索相关的历史记忆",
                    mimeType="application/json"
                ),
                Resource(
                    uri=AnyUrl("claude://memory/inject"),
                    name="上下文注入",
                    description="为提示注入相关上下文",
                    mimeType="application/json"
                ),
                Resource(
                    uri=AnyUrl("claude://memory/status"),
                    name="服务状态",
                    description="获取服务运行状态",
                    mimeType="application/json"
                )
            ]

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出可用工具"""
            return [
                Tool(
                    name="claude_memory_search",
                    description="搜索相关的历史记忆和对话",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索查询文本"
                            },
                            "project_id": {
                                "type": "string",
                                "description": "项目ID，用于跨项目隔离",
                                "default": "default"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20
                            },
                            "min_score": {
                                "type": "number",
                                "description": "最小相关性分数",
                                "default": 0.6,
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "memory_types": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["GLOBAL", "QUICK", "ARCHIVE"]
                                },
                                "description": "记忆类型过滤"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="claude_memory_inject",
                    description="为用户提示注入相关的历史上下文",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "original_prompt": {
                                "type": "string",
                                "description": "原始用户提示"
                            },
                            "query_text": {
                                "type": "string",
                                "description": "用于搜索的查询文本（可选，默认使用原始提示）"
                            },
                            "context_hint": {
                                "type": "string",
                                "description": "上下文提示，帮助更好地理解查询意图"
                            },
                            "injection_mode": {
                                "type": "string",
                                "enum": ["conservative", "balanced", "comprehensive"],
                                "description": "注入模式",
                                "default": "balanced"
                            },
                            "max_tokens": {
                                "type": "integer",
                                "description": "最大Token预算",
                                "default": 2000,
                                "minimum": 500,
                                "maximum": 8000
                            }
                        },
                        "required": ["original_prompt"]
                    }
                ),
                Tool(
                    name="claude_memory_status",
                    description="获取Claude记忆服务的运行状态和指标",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="claude_memory_health",
                    description="执行健康检查，验证服务组件状态",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "detailed": {
                                "type": "boolean",
                                "description": "是否返回详细的健康检查信息",
                                "default": False
                            }
                        }
                    }
                ),
                Tool(
                    name="claude_memory_cross_project_search",
                    description="在多个项目中搜索相关的历史记忆和对话",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索查询文本"
                            },
                            "project_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要搜索的项目ID列表（可选）"
                            },
                            "include_all_projects": {
                                "type": "boolean",
                                "description": "是否搜索所有活跃项目",
                                "default": False
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 100
                            },
                            "merge_strategy": {
                                "type": "string",
                                "enum": ["score", "time", "project"],
                                "description": "结果合并策略",
                                "default": "score"
                            },
                            "max_results_per_project": {
                                "type": "integer",
                                "description": "每个项目的最大结果数",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50
                            },
                            "user_id": {
                                "type": "string",
                                "description": "用户ID，用于权限验证（可选，默认从环境变量获取）"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]

        @self.server.call_tool()
        @handle_exceptions(logger=logger, reraise=True)
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """处理工具调用"""
            
            if not self.service_manager:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Service not initialized",
                        "success": False
                    }, ensure_ascii=False, indent=2)
                )]
            
            try:
                if name == "claude_memory_search":
                    return await self._handle_search(arguments)
                
                elif name == "claude_memory_inject":
                    return await self._handle_inject(arguments)
                
                elif name == "claude_memory_status":
                    return await self._handle_status(arguments)
                
                elif name == "claude_memory_health":
                    return await self._handle_health(arguments)
                
                elif name == "claude_memory_cross_project_search":
                    return await self._handle_cross_project_search(arguments)
                
                else:
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "error": f"Unknown tool: {name}",
                            "success": False
                        }, ensure_ascii=False, indent=2)
                    )]
                    
            except Exception as e:
                logger.error(f"Tool {name} execution failed", error=str(e), arguments=arguments)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e),
                        "success": False,
                        "tool": name
                    }, ensure_ascii=False, indent=2)
                )]

        @self.server.read_resource()
        async def read_resource(uri: AnyUrl) -> str:
            """读取资源"""
            uri_str = str(uri)
            
            if uri_str == "claude://memory/status":
                if self.service_manager:
                    status = await self.service_manager.get_service_status()
                    return status.json(ensure_ascii=False, indent=2)
                else:
                    return json.dumps({"error": "Service not initialized"}, ensure_ascii=False)
            
            return json.dumps({"error": f"Unknown resource: {uri_str}"}, ensure_ascii=False)

    async def _handle_search(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """
        处理记忆搜索
        
        Args:
            arguments: 搜索参数
            
        Returns:
            Sequence[TextContent]: 搜索结果
        """
        query_text = arguments.get("query", "")
        # project_id = arguments.get("project_id", os.getenv("CLAUDE_MEMORY_PROJECT_ID", "global"))  # 已删除：全局共享记忆
        limit = arguments.get("limit", 5)
        min_score = arguments.get("min_score", 0.3)  # 降低默认评分阈值
        memory_types = arguments.get("memory_types")
        
        try:
            # 优先使用API Server
            if self.http_client:
                request_data = {
                    "query": query_text,
                    # "project_id": project_id,  # 已删除：全局共享记忆
                    "limit": limit,
                    "min_score": min_score,
                    "query_type": "hybrid"
                }
                
                response = await self.http_client.post("/memory/search", json=request_data)
                
                if response.status_code == 200:
                    response_data = response.json()
                    # API返回的数据已经是格式化好的
                    return [TextContent(
                        type="text",
                        text=json.dumps(response_data, ensure_ascii=False, indent=2)
                    )]
                else:
                    logger.warning(f"API Server returned {response.status_code}, falling back to ServiceManager")
        except Exception as e:
            logger.warning(f"Failed to call API Server: {e}, falling back to ServiceManager")
        
        # 回退到直接使用ServiceManager
        if self.service_manager:
            # 构建搜索查询
            search_query = SearchQuery(
                query=query_text,
                query_type="hybrid",
                limit=limit,
                min_score=min_score,
                context=""
            )
            
            # 执行搜索（全局共享记忆）
            search_response = await self.service_manager.search_memories(search_query)
            
            # 格式化结果
            results = []
            for result in search_response.results:
                results.append({
                    "id": str(result.memory_unit.id),
                    "title": result.memory_unit.title,
                    "summary": result.memory_unit.summary,
                    "relevance_score": result.relevance_score,
                    "memory_type": result.memory_unit.unit_type.value,
                    "keywords": result.memory_unit.keywords,
                    "created_at": result.memory_unit.created_at.isoformat(),
                    "match_type": result.match_type,
                    "matched_keywords": result.matched_keywords
                })
            
            response_data = {
                "success": True,
                "query": query_text,
                "results": results,
                "total_found": search_response.total_count,
                "search_time_ms": search_response.search_time_ms,
                "metadata": search_response.metadata
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response_data, ensure_ascii=False, indent=2)
            )]
        
        # 如果都失败了
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "Both API Server and ServiceManager are unavailable"
            }, ensure_ascii=False, indent=2)
        )]

    async def _handle_inject(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """
        处理上下文注入
        
        Args:
            arguments: 注入参数
            
        Returns:
            Sequence[TextContent]: 注入结果
        """
        original_prompt = arguments.get("original_prompt", "")
        query_text = arguments.get("query_text")
        context_hint = arguments.get("context_hint")
        injection_mode = arguments.get("injection_mode", "comprehensive")  # 始终使用最大模式
        max_tokens = arguments.get("max_tokens", 999999)  # 无限制
        # project_id = os.getenv("CLAUDE_MEMORY_PROJECT_ID", "global")  # 已删除：全局共享记忆
        
        try:
            # 优先使用API Server
            if self.http_client:
                request_data = {
                    "original_prompt": original_prompt,
                    "query_text": query_text,
                    "context_hint": context_hint,
                    "injection_mode": injection_mode,
                    "max_tokens": max_tokens,
                    # "project_id": project_id  # 已删除：全局共享记忆
                }
                
                response = await self.http_client.post("/memory/inject", json=request_data)
                
                if response.status_code == 200:
                    response_data = response.json()
                    return [TextContent(
                        type="text",
                        text=json.dumps(response_data, ensure_ascii=False, indent=2)
                    )]
                else:
                    logger.warning(f"API Server returned {response.status_code}, falling back to ServiceManager")
        except Exception as e:
            logger.warning(f"Failed to call API Server: {e}, falling back to ServiceManager")
        
        # 回退到直接使用ServiceManager
        if self.service_manager:
            # 构建注入请求 - 无限制模式
            injection_request = ContextInjectionRequest(
                original_prompt=original_prompt,
                query_text=query_text or original_prompt,  # 如果没有query_text就使用original_prompt
                context_hint=context_hint,
                injection_mode="comprehensive",  # 强制使用最大模式
                max_tokens=999999  # 无限制
            )
            
            # 执行上下文注入
            injection_response = await self.service_manager.inject_context(injection_request)
            
            # 格式化结果
            injected_memories = []
            for memory in injection_response.injected_memories:
                injected_memories.append({
                    "id": str(memory.id),
                    "title": memory.title,
                    "summary": memory.summary,
                    "memory_type": memory.unit_type.value,
                    "keywords": memory.keywords,
                    "created_at": memory.created_at.isoformat()
                })
            
            response_data = {
                "success": True,
                "enhanced_prompt": injection_response.enhanced_prompt,
                "injected_memories": injected_memories,
                "tokens_used": injection_response.tokens_used,
                "processing_time_ms": injection_response.processing_time_ms,
                "metadata": injection_response.metadata
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response_data, ensure_ascii=False, indent=2)
            )]
        
        # 如果都失败了
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "Both API Server and ServiceManager are unavailable"
            }, ensure_ascii=False, indent=2)
        )]

    async def _handle_status(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """
        处理状态查询
        
        Args:
            arguments: 状态查询参数
            
        Returns:
            Sequence[TextContent]: 服务状态
        """
        status = await self.service_manager.get_service_status()
        
        response_data = {
            "success": True,
            "status": status.status,
            "version": status.version,
            "started_at": status.started_at.isoformat(),
            "uptime_seconds": status.metrics.uptime_seconds,
            "components": status.components,
            "metrics": {
                "conversations_processed": status.metrics.conversations_processed,
                "memories_created": status.metrics.memories_created,
                "memories_retrieved": status.metrics.memories_retrieved,
                "contexts_injected": status.metrics.contexts_injected,
                "average_response_time_ms": status.metrics.average_response_time_ms,
                "error_count": status.metrics.error_count,
                "memory_usage_mb": status.metrics.memory_usage_mb,
                "cpu_usage_percent": status.metrics.cpu_usage_percent
            },
            "configuration": status.configuration
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(response_data, ensure_ascii=False, indent=2)
        )]

    async def _handle_health(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """
        处理健康检查
        
        Args:
            arguments: 健康检查参数
            
        Returns:
            Sequence[TextContent]: 健康状态
        """
        detailed = arguments.get("detailed", False)
        
        # 执行基本健康检查
        health_status = "healthy"
        issues = []
        
        try:
            # 检查服务管理器
            if not self.service_manager or not self.service_manager.is_running:
                health_status = "unhealthy"
                issues.append("Service manager not running")
            
            # 检查数据库连接
            if self.session_manager:
                try:
                    connection_ok = await self.session_manager.test_connection()
                    if not connection_ok:
                        health_status = "degraded"
                        issues.append("Database connectivity issue")
                except Exception as e:
                    health_status = "degraded"
                    issues.append(f"Database connectivity issue: {str(e)}")
            else:
                health_status = "unhealthy"
                issues.append("Session manager not initialized")
            
            # 如果需要详细信息，检查各个组件
            component_health = {}
            if detailed and self.service_manager:
                status = await self.service_manager.get_service_status()
                for component_name, component_info in status.components.items():
                    component_health[component_name] = {
                        "status": component_info["status"],
                        "active": component_info["active"]
                    }
                    
                    if not component_info["active"]:
                        if health_status == "healthy":
                            health_status = "degraded"
                        issues.append(f"Component {component_name} is not active")
            
        except Exception as e:
            health_status = "unhealthy"
            issues.append(f"Health check failed: {str(e)}")
        
        response_data = {
            "success": True,
            "health_status": health_status,
            "issues": issues,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if detailed:
            response_data["component_health"] = component_health
        
        return [TextContent(
            type="text",
            text=json.dumps(response_data, ensure_ascii=False, indent=2)
        )]

    async def _handle_cross_project_search(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """
        处理跨项目搜索 - 已删除：全局共享记忆，不需要项目隔离
        改为直接使用全局搜索
        """
        query_text = arguments.get("query", "")
        limit = arguments.get("limit", 20)
        min_score = arguments.get("min_score", 0.5)
        
        # 构建搜索查询（全局搜索）
        search_query = SearchQuery(
            query=query_text,
            query_type="hybrid",
            limit=limit,
            min_score=min_score,
            context=""
        )
        
        # 执行全局搜索（替代跨项目搜索）
        search_response = await self.service_manager.search_memories(search_query)
        
        # 格式化结果
        results = []
        for result in search_response.results:
            results.append({
                "id": str(result.memory_unit.id),
                "title": result.memory_unit.title,
                "summary": result.memory_unit.summary,
                "relevance_score": result.relevance_score,
                "memory_type": result.memory_unit.unit_type.value,
                "keywords": result.memory_unit.keywords,
                "created_at": result.memory_unit.created_at.isoformat(),
                "match_type": result.match_type,
                "matched_keywords": result.matched_keywords,
                # "project_id": result.metadata.get("project_id", "global"),  # 已删除：全局共享记忆
                # "project_name": result.metadata.get("project_name", "Global")  # 已删除：全局共享记忆
            })
        
        response_data = {
            "success": True,
            "query": query_text,
            "results": results,
            "total_found": search_response.total_count,
            # "projects_searched": search_response.projects_searched,  # 已删除：全局共享记忆
            # "project_stats": project_stats,  # 已删除：全局共享记忆
            "search_time_ms": search_response.search_time_ms,
            # "merge_strategy": merge_strategy,  # 已删除：全局共享记忆
            "metadata": search_response.metadata
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(response_data, ensure_ascii=False, indent=2)
        )]


async def main():
    """
    主入口函数
    """
    # 重定向stderr到日志文件，避免干扰stdio通信
    sys.stderr = StderrToLogger(logger)
    
    # 创建MCP服务器
    mcp_server = ClaudeMemoryMCPServer()
    
    try:
        # 初始化服务器
        await mcp_server.initialize()
        
        # 配置服务器能力
        init_options = InitializationOptions(
            server_name="claude-memory-mcp",
            server_version="1.0.0",
            capabilities=ServerCapabilities(
                tools={"listChanged": True},
                resources={"listChanged": True}
            )
        )
        
        # 启动stdio服务器
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.server.run(
                read_stream,
                write_stream,
                init_options
            )
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error("MCP server failed", error=str(e))
        sys.exit(1)
    finally:
        await mcp_server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())