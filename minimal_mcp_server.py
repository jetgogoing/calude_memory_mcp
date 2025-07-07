#!/usr/bin/env python3
"""
最小化MCP服务器 - 纯MCP协议实现
"""

import asyncio
import sys
import os
from typing import Any, Dict, List

# 完全静默stderr输出
sys.stderr = open(os.devnull, 'w')

# 安装路径检查
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    sys.exit(1)

class MinimalMCPServer:
    def __init__(self):
        self.server = Server("claude-memory")
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="test_connection",
                    description="测试MCP连接",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            if name == "test_connection":
                return [TextContent(
                    type="text",
                    text="✅ Claude Memory MCP服务连接成功！"
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"未知工具: {name}"
                )]

async def main():
    try:
        server = MinimalMCPServer()
        async with stdio_server() as (read_stream, write_stream):
            await server.server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options={}
            )
    except Exception:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())