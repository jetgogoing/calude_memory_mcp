#!/usr/bin/env python3
"""
稳定版Claude Memory MCP服务器
修复TaskGroup异常问题
"""

import sys
import json
import os
import asyncio
from pathlib import Path
from typing import Any, Dict

# 设置环境
os.environ["PYTHONUNBUFFERED"] = "1"

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def log_to_file(msg):
    """写入日志文件"""
    log_file = "/home/jetgogoing/claude_memory/logs/stable_mcp.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a") as f:
        f.write(f"{msg}\n")
        f.flush()

class StableMCPServer:
    """稳定版MCP服务器 - 修复TaskGroup问题"""
    
    def __init__(self):
        # MCP工具映射
        self.tools = {
            "memory_search": self.memory_search,
            "memory_health": self.memory_health,
            "ping": self.ping
        }
    
    def write_message(self, message: Dict[str, Any]):
        """写入消息到stdout"""
        try:
            output = json.dumps(message, ensure_ascii=False)
            sys.stdout.write(output + "\n")
            sys.stdout.flush()
        except Exception as e:
            log_to_file(f"写入消息失败: {e}")
    
    def write_result(self, request_id: str, result: Any):
        """写入成功响应"""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        self.write_message(response)
    
    def write_error(self, request_id: str, error_msg: str):
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
    
    async def handle_request(self, request: Dict[str, Any]):
        """处理请求"""
        try:
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})
            
            log_to_file(f"处理请求: {method}")
            
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True}
                    },
                    "serverInfo": {
                        "name": "claude-memory",
                        "version": "1.4.0-stable"
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
                    try:
                        result = await self.tools[tool_name](arguments)
                        self.write_result(request_id, {"content": [{"type": "text", "text": result}]})
                    except Exception as e:
                        self.write_error(request_id, f"工具执行失败: {e}")
                else:
                    self.write_error(request_id, f"未知工具: {tool_name}")
            
            elif method == "notifications/initialized":
                # 忽略初始化通知
                pass
            
            else:
                log_to_file(f"未处理的方法: {method}")
        
        except Exception as e:
            log_to_file(f"请求处理错误: {e}")
            if request_id:
                self.write_error(request_id, str(e))
    
    async def ping(self, args):
        """心跳检测"""
        return "pong - Claude Memory MCP服务器运行正常"
    
    async def memory_health(self, args):
        """健康检查"""
        # 检查PostgreSQL
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                database="claude_memory_db", 
                user="claude_memory",
                password="password"
            )
            conn.close()
            postgres_status = "ok"
        except Exception:
            postgres_status = "down"
        
        # 检查Qdrant
        try:
            import requests
            resp = requests.get("http://localhost:6333/cluster", timeout=5)
            qdrant_status = "ok" if resp.status_code == 200 else "down"
        except Exception:
            qdrant_status = "down"
        
        return f"""🏥 Claude Memory健康检查

✅ MCP服务器: 运行正常
{'✅' if postgres_status == 'ok' else '❌'} PostgreSQL: {postgres_status}
{'✅' if qdrant_status == 'ok' else '❌'} Qdrant: {qdrant_status}

🚀 服务状态: {'全部正常' if all(s == 'ok' for s in [postgres_status, qdrant_status]) else '部分异常'}"""
    
    async def memory_search(self, args):
        """记忆搜索"""
        query = args.get("query", "")
        limit = args.get("limit", 5)
        
        # 简单的数据库搜索
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                database="claude_memory_db",
                user="claude_memory", 
                password="password"
            )
            cur = conn.cursor()
            cur.execute("SELECT content FROM messages WHERE content ILIKE %s LIMIT %s", (f"%{query}%", limit))
            results = cur.fetchall()
            conn.close()
            
            if results:
                content = "\n".join([f"• {row[0]}" for row in results])
                return f"🔍 找到 {len(results)} 条相关记忆:\n\n{content}"
            else:
                return f"🔍 未找到包含 '{query}' 的记忆"
        
        except Exception as e:
            return f"❌ 搜索失败: {e}"
    
    async def run(self):
        """运行MCP服务器"""
        log_to_file("=== STABLE MCP SERVER STARTING ===")
        
        # 发送ready信号
        ready_msg = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        self.write_message(ready_msg)
        log_to_file("✅ Ready信号发送成功")
        
        # 主循环
        try:
            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                
                try:
                    request = json.loads(line.strip())
                    await self.handle_request(request)
                except json.JSONDecodeError:
                    log_to_file(f"JSON解析错误: {line}")
                except Exception as e:
                    log_to_file(f"处理错误: {e}")
        
        except KeyboardInterrupt:
            log_to_file("服务器收到中断信号")
        except Exception as e:
            log_to_file(f"服务器异常: {e}")
        
        log_to_file("=== STABLE MCP SERVER STOPPED ===")

async def main():
    """主函数"""
    server = StableMCPServer()
    await server.run()

if __name__ == "__main__":
    # 避免TaskGroup问题，使用简单的asyncio.run
    try:
        asyncio.run(main())
    except Exception as e:
        log_to_file(f"启动失败: {e}")
        sys.exit(1)