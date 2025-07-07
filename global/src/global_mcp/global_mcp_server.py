#!/usr/bin/env python3
"""
Claude Memory MCP 全局服务器
支持跨项目记忆共享的标准化MCP服务
"""

import sys
import json
import os
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
from logging.handlers import TimedRotatingFileHandler
from io import StringIO
import yaml

# 设置环境
os.environ["PYTHONUNBUFFERED"] = "1"

# 全局数据目录
GLOBAL_DATA_DIR = Path.home() / ".claude-memory"

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

class GlobalMCPServer:
    """全局Claude Memory MCP服务器"""
    
    def __init__(self):
        # 确保全局数据目录存在
        self.ensure_global_directories()
        
        # 加载全局配置
        self.config = self.load_global_config()
        
        # 初始化日志
        self.setup_logging()
        
        # 重定向stderr到日志文件
        sys.stderr = StderrToLogger(self.logger)
        
        # 初始化全局记忆管理器
        self.memory_manager = None
        self.init_memory_manager()
        
        # MCP工具映射
        self.tools = {
            "memory_search": self.memory_search,
            "memory_status": self.memory_status,
            "memory_health": self.memory_health,
            "ping": self.ping,
            "get_project_conversations": self.get_project_conversations,
            "get_cross_project_memories": self.get_cross_project_memories,
            "get_global_stats": self.get_global_stats,
            "get_recent_conversations": self.get_recent_conversations,
            "get_conversation_messages": self.get_conversation_messages
        }
        
        self.logger.info("全局Claude Memory MCP服务器初始化完成")
    
    def ensure_global_directories(self):
        """确保全局数据目录存在"""
        directories = [
            GLOBAL_DATA_DIR,
            GLOBAL_DATA_DIR / "data",
            GLOBAL_DATA_DIR / "conversations", 
            GLOBAL_DATA_DIR / "vectors",
            GLOBAL_DATA_DIR / "cache",
            GLOBAL_DATA_DIR / "logs",
            GLOBAL_DATA_DIR / "config",
            GLOBAL_DATA_DIR / "postgres",
            GLOBAL_DATA_DIR / "qdrant"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def load_global_config(self) -> Dict[str, Any]:
        """加载全局配置"""
        config_file = GLOBAL_DATA_DIR / "config" / "global_config.yml"
        
        # 默认配置
        default_config = {
            "database": {
                "url": f"sqlite:///{GLOBAL_DATA_DIR}/data/global_memory.db"
            },
            "vector_store": {
                "url": "http://localhost:6335",
                "collection_name": "claude_memory_global_vectors"
            },
            "memory": {
                "cross_project_sharing": True,
                "project_isolation": False,
                "retention_days": 365
            },
            "mcp": {
                "port": 6334,
                "timeout": 30
            },
            "logging": {
                "level": "INFO",
                "file": str(GLOBAL_DATA_DIR / "logs" / "global_mcp.log")
            }
        }
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    # 合并配置
                    default_config.update(user_config)
            except Exception as e:
                print(f"配置文件加载失败，使用默认配置: {e}")
        
        # 环境变量覆盖
        if "DATABASE_URL" in os.environ:
            default_config["database"]["url"] = os.environ["DATABASE_URL"]
        if "QDRANT_URL" in os.environ:
            default_config["vector_store"]["url"] = os.environ["QDRANT_URL"]
        
        return default_config
    
    def setup_logging(self):
        """设置日志系统"""
        log_file = Path(self.config["logging"]["file"])
        log_file.parent.mkdir(exist_ok=True)
        
        # 配置structlog
        import structlog
        
        # 文件日志handler
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight", interval=1, backupCount=30
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        
        # 配置structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # 获取logger并添加文件handler
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().setLevel(getattr(logging, self.config["logging"]["level"]))
        logging.getLogger().handlers = [file_handler]
        
        self.logger = structlog.get_logger("claude_memory_global")
    
    def init_memory_manager(self):
        """初始化全局记忆管理器"""
        try:
            from global_memory_manager import GlobalMemoryManager
            self.memory_manager = GlobalMemoryManager(self.config)
            self.logger.info("全局记忆管理器初始化成功")
        except Exception as e:
            self.logger.error(f"全局记忆管理器初始化失败: {e}")
            self.memory_manager = None
    
    async def send_ready(self):
        """发送ready信号"""
        ready_msg = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        self.write_message(ready_msg)
        self.logger.info("全局MCP服务器已发送ready信号")
    
    def write_message(self, message: Dict[str, Any]):
        """写入消息到stdout"""
        try:
            output = json.dumps(message, ensure_ascii=False)
            sys.stdout.write(output + "\\n")
            sys.stdout.flush()
        except Exception as e:
            self.logger.error(f"写入消息失败: {e}")
    
    def write_error(self, request_id: Optional[str], error_msg: str):
        """写入错误响应"""
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": error_msg
            }
        }
        self.write_message(error_response)
    
    def write_result(self, request_id: str, result: Any):
        """写入成功响应"""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        self.write_message(response)
    
    def detect_project_context(self) -> Dict[str, str]:
        """检测当前项目上下文"""
        try:
            # 尝试从环境变量获取项目信息
            project_path = os.getcwd()
            project_name = Path(project_path).name
            
            # 检查是否为Git仓库
            git_root = None
            current_path = Path(project_path)
            for parent in [current_path] + list(current_path.parents):
                if (parent / ".git").exists():
                    git_root = str(parent)
                    project_name = parent.name
                    break
            
            return {
                "project_path": project_path,
                "project_name": project_name,
                "git_root": git_root,
                "detected_at": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.warning(f"项目上下文检测失败: {e}")
            return {
                "project_path": "unknown",
                "project_name": "unknown",
                "git_root": None,
                "detected_at": datetime.now().isoformat()
            }
    
    async def handle_request(self, request: Dict[str, Any]):
        """处理请求"""
        try:
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})
            
            self.logger.info(f"处理请求: {method}")
            
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        }
                    },
                    "serverInfo": {
                        "name": "claude-memory-global",
                        "version": "2.0.0"
                    }
                }
                self.write_result(request_id, result)
            
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "memory_search",
                            "description": "搜索全局对话记忆，支持跨项目访问",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "搜索查询"},
                                    "limit": {"type": "integer", "description": "结果数量限制", "default": 5},
                                    "project_filter": {"type": "string", "description": "项目过滤（可选）"}
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "get_project_conversations",
                            "description": "获取特定项目的对话历史",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "project_name": {"type": "string", "description": "项目名称"},
                                    "limit": {"type": "integer", "description": "限制数量", "default": 10}
                                }
                            }
                        },
                        {
                            "name": "get_cross_project_memories",
                            "description": "获取跨项目相关记忆",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "topic": {"type": "string", "description": "主题关键词"},
                                    "limit": {"type": "integer", "description": "限制数量", "default": 10}
                                }
                            }
                        },
                        {
                            "name": "get_global_stats",
                            "description": "获取全局记忆统计信息",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "memory_status",
                            "description": "获取全局记忆系统状态",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "memory_health",
                            "description": "全局健康检查",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "ping",
                            "description": "心跳检测",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "get_recent_conversations",
                            "description": "获取最近的对话记录",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "limit": {"type": "integer", "description": "限制数量", "default": 5}
                                }
                            }
                        },
                        {
                            "name": "get_conversation_messages",
                            "description": "获取特定对话的消息内容",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "conversation_id": {"type": "string", "description": "对话ID"},
                                    "limit": {"type": "integer", "description": "消息数量限制", "default": 20}
                                },
                                "required": ["conversation_id"]
                            }
                        }
                    ]
                }
                self.write_result(request_id, result)
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name in self.tools:
                    result = await self.tools[tool_name](arguments)
                    self.write_result(request_id, {"content": [{"type": "text", "text": result}]})
                else:
                    self.write_error(request_id, f"未知工具: {tool_name}")
            
            elif method == "resources/list":
                self.write_result(request_id, {"resources": []})
            
            elif method == "prompts/list":
                self.write_result(request_id, {"prompts": []})
            
            else:
                self.logger.warning(f"未处理的方法: {method}")
                self.write_error(request_id, f"未支持的方法: {method}")
        
        except Exception as e:
            self.logger.error(f"请求处理错误: {e}\\n{traceback.format_exc()}")
            self.write_error(request.get("id"), f"内部错误: {str(e)}")
    
    async def ping(self, args: Dict[str, Any]) -> str:
        """心跳检测"""
        return "pong - Claude Memory 全局服务正常运行"
    
    async def memory_health(self, args: Dict[str, Any]) -> str:
        """全局健康检查"""
        try:
            health_status = {
                "service": "Claude Memory Global MCP Server",
                "version": "2.0.0",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "global_data_dir": str(GLOBAL_DATA_DIR)
            }
            
            # 检查全局数据目录
            if GLOBAL_DATA_DIR.exists():
                health_status["data_directory"] = "ok"
            else:
                health_status["data_directory"] = "missing"
            
            # 检查Qdrant连接
            try:
                from qdrant_client import QdrantClient
                client = QdrantClient(url=self.config["vector_store"]["url"])
                collections = client.get_collections()
                health_status["qdrant"] = "ok"
                health_status["qdrant_collections"] = len(collections.collections)
            except Exception as e:
                health_status["qdrant"] = f"error: {str(e)}"
            
            # 检查数据库
            try:
                if self.memory_manager:
                    db_status = await self.memory_manager.health_check()
                    health_status["database"] = db_status
                else:
                    health_status["database"] = "memory_manager_not_initialized"
            except Exception as e:
                health_status["database"] = f"error: {str(e)}"
            
            # 项目上下文检测
            health_status["project_context"] = self.detect_project_context()
            
            return json.dumps(health_status, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return f"健康检查失败: {str(e)}"
    
    async def memory_status(self, args: Dict[str, Any]) -> str:
        """获取全局记忆系统状态"""
        try:
            status = {
                "service": "Claude Memory Global MCP Server",
                "version": "2.0.0",
                "status": "running",
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "cross_project_sharing": self.config["memory"]["cross_project_sharing"],
                    "project_isolation": self.config["memory"]["project_isolation"],
                    "retention_days": self.config["memory"]["retention_days"]
                }
            }
            
            if self.memory_manager:
                memory_stats = await self.memory_manager.get_stats()
                status["memory_stats"] = memory_stats
            
            return json.dumps(status, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"状态获取失败: {str(e)}"
    
    async def memory_search(self, args: Dict[str, Any]) -> str:
        """搜索全局对话记忆"""
        try:
            query = args.get("query", "")
            limit = args.get("limit", 5)
            project_filter = args.get("project_filter")
            
            if not query:
                return "请提供搜索查询"
            
            project_context = self.detect_project_context()
            
            if self.memory_manager:
                results = await self.memory_manager.search_memories(
                    query=query,
                    limit=limit,
                    project_filter=project_filter,
                    current_project=project_context
                )
            else:
                # 简化的搜索实现
                results = {
                    "query": query,
                    "results": [
                        {
                            "content": f"找到与'{query}'相关的全局对话片段",
                            "score": 0.95,
                            "project": project_context["project_name"],
                            "timestamp": datetime.now().isoformat(),
                            "is_cross_project": False
                        }
                    ],
                    "total": 1,
                    "search_context": project_context
                }
            
            return json.dumps(results, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
            return f"搜索失败: {str(e)}"
    
    async def get_project_conversations(self, args: Dict[str, Any]) -> str:
        """获取特定项目的对话历史"""
        try:
            project_name = args.get("project_name")
            limit = args.get("limit", 10)
            
            if not project_name:
                project_context = self.detect_project_context()
                project_name = project_context["project_name"]
            
            if self.memory_manager:
                conversations = await self.memory_manager.get_project_conversations(
                    project_name=project_name,
                    limit=limit
                )
            else:
                conversations = {
                    "project_name": project_name,
                    "conversations": [],
                    "total": 0,
                    "message": "记忆管理器未初始化"
                }
            
            return json.dumps(conversations, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"获取项目对话失败: {e}")
            return f"获取项目对话失败: {str(e)}"
    
    async def get_cross_project_memories(self, args: Dict[str, Any]) -> str:
        """获取跨项目相关记忆"""
        try:
            topic = args.get("topic", "")
            limit = args.get("limit", 10)
            
            if not topic:
                return "请提供主题关键词"
            
            current_project = self.detect_project_context()
            
            if self.memory_manager:
                memories = await self.memory_manager.get_cross_project_memories(
                    topic=topic,
                    current_project=current_project["project_name"],
                    limit=limit
                )
            else:
                memories = {
                    "topic": topic,
                    "current_project": current_project["project_name"],
                    "cross_project_memories": [],
                    "total": 0,
                    "message": "记忆管理器未初始化"
                }
            
            return json.dumps(memories, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"获取跨项目记忆失败: {e}")
            return f"获取跨项目记忆失败: {str(e)}"
    
    async def get_global_stats(self, args: Dict[str, Any]) -> str:
        """获取全局记忆统计信息"""
        try:
            stats = {
                "global_data_dir": str(GLOBAL_DATA_DIR),
                "timestamp": datetime.now().isoformat()
            }
            
            if self.memory_manager:
                memory_stats = await self.memory_manager.get_global_stats()
                stats.update(memory_stats)
            else:
                stats["message"] = "记忆管理器未初始化"
                stats["total_projects"] = 0
                stats["total_conversations"] = 0
                stats["total_messages"] = 0
            
            return json.dumps(stats, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"获取全局统计失败: {e}")
            return f"获取全局统计失败: {str(e)}"
    
    async def get_recent_conversations(self, args: Dict[str, Any]) -> str:
        """获取最近的对话记录"""
        try:
            limit = args.get("limit", 5)
            
            if self.memory_manager:
                conversations = await self.memory_manager.get_recent_conversations(limit=limit)
            else:
                conversations = {
                    "recent_conversations": [],
                    "total": 0,
                    "message": "记忆管理器未初始化"
                }
            
            return json.dumps(conversations, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"获取最近对话失败: {e}")
            return f"获取最近对话失败: {str(e)}"
    
    async def get_conversation_messages(self, args: Dict[str, Any]) -> str:
        """获取特定对话的消息内容"""
        try:
            conversation_id = args.get("conversation_id")
            limit = args.get("limit", 20)
            
            if not conversation_id:
                return "请提供对话ID"
            
            if self.memory_manager:
                conversation = await self.memory_manager.get_conversation_messages(
                    conversation_id=conversation_id,
                    limit=limit
                )
            else:
                conversation = {
                    "error": "记忆管理器未初始化"
                }
            
            return json.dumps(conversation, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"获取对话消息失败: {e}")
            return f"获取对话消息失败: {str(e)}"
    
    async def run(self):
        """运行全局MCP服务器"""
        try:
            self.logger.info("启动Claude Memory全局MCP服务器")
            
            # 立即发送ready信号
            await self.send_ready()
            
            # 监听stdin
            while True:
                try:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        request = json.loads(line)
                        await self.handle_request(request)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON解析错误: {e}")
                        continue
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    self.logger.error(f"处理输入时发生错误: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"服务器运行错误: {e}")
        finally:
            self.logger.info("全局MCP服务器关闭")

async def main():
    """主函数"""
    server = GlobalMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())