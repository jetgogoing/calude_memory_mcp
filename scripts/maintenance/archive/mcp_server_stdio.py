#!/usr/bin/env python3
"""
Claude Memory MCP服务器 - STDIO模式启动入口
专门用于Claude CLI集成
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加src到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

async def main():
    """启动MCP服务器的STDIO模式"""
    try:
        from claude_memory.mcp_server import ClaudeMemoryMCPServer
        from mcp.server.stdio import stdio_server
        
        # 创建MCP服务器实例
        mcp_server_instance = ClaudeMemoryMCPServer()
        
        # 初始化服务器
        await mcp_server_instance.initialize()
        
        # 运行STDIO服务器
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server_instance.server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options={}
            )
            
    except Exception as e:
        print(f"MCP Server startup failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())