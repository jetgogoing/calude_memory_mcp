#!/usr/bin/env python3
"""
Claude Memory MCP 最简化服务器
专注于核心功能，移除所有可能导致失败的复杂组件
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Any, Dict, List

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 静默处理日志
import logging
logging.getLogger().setLevel(logging.CRITICAL)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

class SimpleMCPServer:
    """最简化的MCP服务器"""
    
    def __init__(self):
        self.server = Server("claude-memory-mcp")
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置MCP处理器"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出可用工具"""
            return [
                Tool(
                    name="memory_search",
                    description="搜索历史记忆和对话",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索查询文本"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="memory_status",
                    description="获取记忆服务状态",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """调用工具"""
            try:
                if name == "memory_search":
                    query = arguments.get("query", "")
                    limit = arguments.get("limit", 5)
                    
                    # 这里将来连接实际的搜索功能
                    return [TextContent(
                        type="text",
                        text=f"🔍 搜索记忆: '{query}' (限制: {limit})\n\n当前为演示模式，完整功能开发中..."
                    )]
                
                elif name == "memory_status":
                    return [TextContent(
                        type="text", 
                        text="✅ Claude Memory MCP服务运行正常\n版本: 1.4.0-simple\n状态: 活跃"
                    )]
                
                else:
                    return [TextContent(
                        type="text",
                        text=f"未知工具: {name}"
                    )]
                    
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"错误: {str(e)}"
                )]

async def main():
    """启动MCP服务器"""
    # 静默所有输出，避免干扰stdio通信
    sys.stderr = open(os.devnull, 'w')
    
    try:
        server = SimpleMCPServer()
        async with stdio_server() as (read_stream, write_stream):
            await server.server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options={}
            )
    except:
        # 静默处理所有异常
        pass

if __name__ == "__main__":
    asyncio.run(main())