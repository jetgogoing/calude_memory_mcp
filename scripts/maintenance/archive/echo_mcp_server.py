#!/usr/bin/env python3
"""
最简单的Echo MCP服务器 - 用于测试Claude CLI连接
"""

import sys
import json
import os

# 设置无缓冲
os.environ["PYTHONUNBUFFERED"] = "1"

def log_to_file(msg):
    """写入日志文件而不是stderr"""
    with open("/home/jetgogoing/claude_memory/logs/echo_mcp.log", "a") as f:
        f.write(f"{msg}\n")
        f.flush()

try:
    log_to_file("=== ECHO MCP SERVER START ===")
    
    # 立即发送ready信号
    ready_msg = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    sys.stdout.write(json.dumps(ready_msg) + "\n")
    sys.stdout.flush()
    log_to_file("✅ Ready signal sent")
    
    # 简单的消息循环
    for line_num, line in enumerate(sys.stdin):
        try:
            log_to_file(f"收到消息 {line_num}: {line.strip()}")
            
            if not line.strip():
                continue
                
            req = json.loads(line.strip())
            req_id = req.get("id", 1)
            method = req.get("method", "unknown")
            
            log_to_file(f"解析请求: method={method}, id={req_id}")
            
            # 根据方法类型响应
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "claude-memory-echo",
                            "version": "1.0.0"
                        }
                    }
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "echo_test",
                                "description": "Echo测试工具",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {}
                                }
                            }
                        ]
                    }
                }
            elif method == "tools/call":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": "✅ Echo MCP服务器连接成功！Claude CLI通信正常。"
                            }
                        ]
                    }
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            # 发送响应
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            log_to_file(f"✅ 已发送响应: {method}")
            
        except json.JSONDecodeError as e:
            log_to_file(f"❌ JSON解析错误: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()
            
        except Exception as e:
            log_to_file(f"❌ 处理错误: {e}")
            break

except Exception as e:
    log_to_file(f"❌ Fatal error: {e}")
    sys.exit(1)

log_to_file("=== ECHO MCP SERVER EXIT ===")