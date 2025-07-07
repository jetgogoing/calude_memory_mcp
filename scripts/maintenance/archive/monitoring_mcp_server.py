#!/usr/bin/env python3
"""
监控增强版Claude Memory MCP服务器
添加Prometheus指标支持
"""

import sys
import json
import os
import asyncio
import time
import threading
from pathlib import Path
from typing import Any, Dict
from http.server import HTTPServer, BaseHTTPRequestHandler

# 设置环境
os.environ["PYTHONUNBUFFERED"] = "1"

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def log_to_file(msg):
    """写入日志文件"""
    log_file = "/home/jetgogoing/claude_memory/logs/monitoring_mcp.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        f.flush()

class PrometheusMetrics:
    """Prometheus指标收集器"""
    
    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.postgres_status = 0  # 0=down, 1=up
        self.qdrant_status = 0    # 0=down, 1=up
        self.memory_search_count = 0
        self.health_check_count = 0
        self.last_health_check_time = 0
        self.response_times = []
        
    def record_request(self):
        """记录请求"""
        self.request_count += 1
        
    def record_postgres_status(self, status):
        """记录PostgreSQL状态"""
        self.postgres_status = 1 if status == "ok" else 0
        
    def record_qdrant_status(self, status):
        """记录Qdrant状态"""
        self.qdrant_status = 1 if status == "ok" else 0
        
    def record_memory_search(self):
        """记录内存搜索"""
        self.memory_search_count += 1
        
    def record_health_check(self):
        """记录健康检查"""
        self.health_check_count += 1
        self.last_health_check_time = time.time()
        
    def record_response_time(self, duration):
        """记录响应时间"""
        self.response_times.append(duration)
        # 只保留最近100条记录
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]
    
    def get_metrics(self):
        """生成Prometheus格式的指标"""
        uptime = time.time() - self.start_time
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        
        metrics = f"""# HELP claude_memory_uptime_seconds MCP服务器运行时间
# TYPE claude_memory_uptime_seconds counter
claude_memory_uptime_seconds {uptime}

# HELP claude_memory_requests_total MCP请求总数
# TYPE claude_memory_requests_total counter
claude_memory_requests_total {self.request_count}

# HELP claude_memory_postgres_up PostgreSQL服务状态
# TYPE claude_memory_postgres_up gauge
claude_memory_postgres_up {self.postgres_status}

# HELP claude_memory_qdrant_up Qdrant服务状态
# TYPE claude_memory_qdrant_up gauge
claude_memory_qdrant_up {self.qdrant_status}

# HELP claude_memory_search_total 记忆搜索总数
# TYPE claude_memory_search_total counter
claude_memory_search_total {self.memory_search_count}

# HELP claude_memory_health_checks_total 健康检查总数
# TYPE claude_memory_health_checks_total counter
claude_memory_health_checks_total {self.health_check_count}

# HELP claude_memory_last_health_check_timestamp 最后健康检查时间戳
# TYPE claude_memory_last_health_check_timestamp gauge
claude_memory_last_health_check_timestamp {self.last_health_check_time}

# HELP claude_memory_avg_response_time_seconds 平均响应时间
# TYPE claude_memory_avg_response_time_seconds gauge
claude_memory_avg_response_time_seconds {avg_response_time}

# HELP claude_memory_service_info 服务信息
# TYPE claude_memory_service_info gauge
claude_memory_service_info{{version="1.4.0-monitoring"}} 1
"""
        return metrics

class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP指标处理器"""
    
    def __init__(self, metrics, *args, **kwargs):
        self.metrics = metrics
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """处理GET请求"""
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(self.metrics.get_metrics().encode('utf-8'))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            health_data = {
                "status": "healthy",
                "postgres": bool(self.metrics.postgres_status),
                "qdrant": bool(self.metrics.qdrant_status),
                "uptime": time.time() - self.metrics.start_time
            }
            self.wfile.write(json.dumps(health_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """禁用默认日志"""
        pass

class MonitoringMCPServer:
    """监控增强版MCP服务器"""
    
    def __init__(self):
        # MCP工具映射
        self.tools = {
            "memory_search": self.memory_search,
            "memory_health": self.memory_health,
            "ping": self.ping
        }
        
        # 初始化指标收集器
        self.metrics = PrometheusMetrics()
        
        # 启动HTTP指标服务器
        self.start_metrics_server()
    
    def start_metrics_server(self):
        """启动HTTP指标服务器"""
        try:
            def handler(*args, **kwargs):
                return MetricsHandler(self.metrics, *args, **kwargs)
            
            server = HTTPServer(('localhost', 8080), handler)
            
            def run_server():
                log_to_file("✅ Prometheus指标服务器启动在 http://localhost:8080/metrics")
                server.serve_forever()
            
            # 在后台线程中运行HTTP服务器
            thread = threading.Thread(target=run_server, daemon=True)
            thread.start()
            
        except Exception as e:
            log_to_file(f"❌ 指标服务器启动失败: {e}")
    
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
        start_time = time.time()
        try:
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})
            
            # 记录请求指标
            self.metrics.record_request()
            log_to_file(f"处理请求: {method}")
            
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True}
                    },
                    "serverInfo": {
                        "name": "claude-memory-monitoring",
                        "version": "1.4.0-monitoring"
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
                            "description": "健康检查和指标端点",
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
        
        finally:
            # 记录响应时间
            duration = time.time() - start_time
            self.metrics.record_response_time(duration)
    
    async def ping(self, args):
        """心跳检测"""
        return "pong - Claude Memory MCP监控服务器运行正常"
    
    async def memory_health(self, args):
        """健康检查和指标信息"""
        self.metrics.record_health_check()
        
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
        
        # 记录PostgreSQL状态
        self.metrics.record_postgres_status(postgres_status)
        
        # 检查Qdrant
        try:
            import requests
            resp = requests.get("http://localhost:6333/cluster", timeout=5)
            qdrant_status = "ok" if resp.status_code == 200 else "down"
        except Exception:
            qdrant_status = "down"
        
        # 记录Qdrant状态
        self.metrics.record_qdrant_status(qdrant_status)
        
        # 计算运行时间
        uptime = time.time() - self.metrics.start_time
        uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s"
        
        return f"""🏥 Claude Memory健康检查 & 监控

✅ MCP服务器: 运行正常 (运行时间: {uptime_str})
{'✅' if postgres_status == 'ok' else '❌'} PostgreSQL: {postgres_status}
{'✅' if qdrant_status == 'ok' else '❌'} Qdrant: {qdrant_status}

📊 统计数据:
• 总请求数: {self.metrics.request_count}
• 记忆搜索: {self.metrics.memory_search_count}次
• 健康检查: {self.metrics.health_check_count}次

🔗 监控端点:
• Prometheus指标: http://localhost:8080/metrics
• 健康检查API: http://localhost:8080/health

🚀 服务状态: {'全部正常' if all(s == 'ok' for s in [postgres_status, qdrant_status]) else '部分异常'}"""
    
    async def memory_search(self, args):
        """记忆搜索"""
        self.metrics.record_memory_search()
        
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
        log_to_file("=== MONITORING MCP SERVER STARTING ===")
        
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
        
        log_to_file("=== MONITORING MCP SERVER STOPPED ===")

async def main():
    """主函数"""
    server = MonitoringMCPServer()
    await server.run()

if __name__ == "__main__":
    # 避免TaskGroup问题，使用简单的asyncio.run
    try:
        asyncio.run(main())
    except Exception as e:
        log_to_file(f"启动失败: {e}")
        sys.exit(1)