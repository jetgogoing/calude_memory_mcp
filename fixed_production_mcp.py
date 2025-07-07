#!/usr/bin/env python3
"""
Claude Memory MCP服务器 - 修复版本
解决stdio通信问题，确保日志不干扰MCP协议
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

# 设置环境
os.environ["PYTHONUNBUFFERED"] = "1"

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

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

class ProductionMCPServer:
    """生产级MCP服务器 - stdio通信优化版本"""
    
    def __init__(self):
        # 初始化日志
        self.setup_logging()
        
        # 重定向stderr到日志文件
        sys.stderr = StderrToLogger(self.logger)
        
        # MCP工具映射
        self.tools = {
            "memory_search": self.memory_search,
            "memory_status": self.memory_status,
            "memory_health": self.memory_health,
            "ping": self.ping
        }
    
    def setup_logging(self):
        """设置日志系统，只写文件不输出到控制台"""
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 配置structlog只写入文件
        import structlog
        
        # 文件日志handler
        file_handler = TimedRotatingFileHandler(
            log_dir / "mcp_production.log",
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
        logging.getLogger().setLevel(logging.INFO)
        
        # 禁用控制台输出
        logging.getLogger().handlers = [file_handler]
        
        self.logger = structlog.get_logger("claude_memory_mcp")
    
    async def send_ready(self):
        """发送ready信号"""
        ready_msg = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        self.write_message(ready_msg)
        self.logger.info("MCP服务器已发送ready信号")
    
    def write_message(self, message: Dict[str, Any]):
        """写入消息到stdout"""
        try:
            output = json.dumps(message, ensure_ascii=False)
            sys.stdout.write(output + "\n")
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
                        "name": "claude-memory",
                        "version": "1.4.0"
                    }
                }
                self.write_result(request_id, result)
            
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "memory_search",
                            "description": "搜索对话记忆",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "搜索查询"},
                                    "limit": {"type": "integer", "description": "结果数量限制", "default": 5}
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "memory_status",
                            "description": "获取记忆系统状态",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "memory_health",
                            "description": "健康检查",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "ping",
                            "description": "心跳检测",
                            "inputSchema": {"type": "object", "properties": {}}
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
            self.logger.error(f"请求处理错误: {e}\n{traceback.format_exc()}")
            self.write_error(request.get("id"), f"内部错误: {str(e)}")
    
    async def ping(self, args: Dict[str, Any]) -> str:
        """心跳检测"""
        return "pong"
    
    async def memory_health(self, args: Dict[str, Any]) -> str:
        """健康检查"""
        try:
            health_status = {"service": "ok", "timestamp": datetime.now().isoformat()}
            
            # 检查Qdrant连接
            try:
                from qdrant_client import QdrantClient
                client = QdrantClient(host="localhost", port=6333)
                collections = client.get_collections()
                health_status["qdrant"] = "ok"
            except Exception as e:
                health_status["qdrant"] = f"error: {str(e)}"
            
            # 检查数据库
            try:
                import sqlite3
                db_path = Path(__file__).parent / "data" / "claude_memory.db"
                if db_path.exists():
                    conn = sqlite3.connect(db_path)
                    conn.execute("SELECT 1")
                    conn.close()
                    health_status["database"] = "ok"
                else:
                    health_status["database"] = "file not found"
            except Exception as e:
                health_status["database"] = f"error: {str(e)}"
            
            return json.dumps(health_status, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return f"健康检查失败: {str(e)}"
    
    async def memory_status(self, args: Dict[str, Any]) -> str:
        """获取记忆系统状态"""
        try:
            status = {
                "service": "Claude Memory MCP Server",
                "version": "1.4.0",
                "status": "running",
                "timestamp": datetime.now().isoformat()
            }
            return json.dumps(status, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"状态获取失败: {str(e)}"
    
    async def memory_search(self, args: Dict[str, Any]) -> str:
        """搜索对话记忆"""
        try:
            query = args.get("query", "")
            limit = args.get("limit", 5)
            
            # 简化的搜索实现
            if not query:
                return "请提供搜索查询"
            
            # 这里应该实现真正的向量搜索
            # 为了演示，返回模拟结果
            results = {
                "query": query,
                "results": [
                    {
                        "content": f"找到与'{query}'相关的对话片段",
                        "score": 0.95,
                        "timestamp": datetime.now().isoformat()
                    }
                ],
                "total": 1
            }
            
            return json.dumps(results, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
            return f"搜索失败: {str(e)}"
    
    async def run(self):
        """运行MCP服务器"""
        try:
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
            self.logger.info("MCP服务器关闭")

async def main():
    """主函数"""
    server = ProductionMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())