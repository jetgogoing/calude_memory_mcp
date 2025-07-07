#!/usr/bin/env python3
"""
调试版MCP服务器 - 捕获所有错误信息
"""

import asyncio
import sys
import os
import json
import traceback
from typing import Any, Dict, List

# 设置环境
os.environ["PYTHONUNBUFFERED"] = "1"

# 创建详细日志
log_file = "/home/jetgogoing/claude_memory/logs/debug_mcp.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)

def log_error(msg):
    """记录错误到文件"""
    with open(log_file, "a") as f:
        f.write(f"{msg}\n")
        f.flush()

try:
    log_error("=== DEBUG MCP SERVER STARTING ===")
    
    # 测试基础导入
    log_error("Testing imports...")
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    log_error("✅ MCP imports successful")
    
    class DebugMCPServer:
        def __init__(self):
            log_error("Initializing DebugMCPServer...")
            self.server = Server("claude-memory-debug")
            self._setup_handlers()
            log_error("✅ Server initialized")
        
        def _setup_handlers(self):
            log_error("Setting up handlers...")
            
            @self.server.list_tools()
            async def list_tools() -> List[Tool]:
                log_error("list_tools called")
                return [
                    Tool(
                        name="debug_test",
                        description="调试测试工具",
                        inputSchema={
                            "type": "object",
                            "properties": {}
                        }
                    )
                ]
            
            @self.server.call_tool()
            async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
                log_error(f"call_tool called: {name}")
                return [TextContent(
                    type="text",
                    text=f"✅ 调试工具 {name} 调用成功！服务器运行正常。"
                )]
            
            log_error("✅ Handlers setup complete")

    async def main():
        log_error("Starting main function...")
        try:
            server = DebugMCPServer()
            log_error("✅ Server instance created")
            
            async with stdio_server() as (read_stream, write_stream):
                log_error("✅ STDIO server started")
                await server.server.run(
                    read_stream=read_stream,
                    write_stream=write_stream,
                    initialization_options={}
                )
                
        except Exception as e:
            log_error(f"❌ Error in main: {e}")
            log_error(f"Traceback: {traceback.format_exc()}")
            raise

    if __name__ == "__main__":
        log_error("Starting asyncio.run...")
        try:
            asyncio.run(main())
        except Exception as e:
            log_error(f"❌ Fatal error: {e}")
            log_error(f"Full traceback: {traceback.format_exc()}")
            sys.exit(1)

except Exception as e:
    log_error(f"❌ Import or initialization error: {e}")
    log_error(f"Full traceback: {traceback.format_exc()}")
    sys.exit(1)