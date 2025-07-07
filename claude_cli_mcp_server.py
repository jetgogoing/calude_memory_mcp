#!/usr/bin/env python3
"""
Claude CLI专用MCP服务器
专门为Claude CLI集成优化，移除复杂的后台任务
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from mcp.server.stdio import stdio_server
from claude_memory.mcp_server import ClaudeMemoryMCPServer


async def main():
    """启动Claude CLI专用MCP服务器"""
    
    # 创建MCP服务器
    server = ClaudeMemoryMCPServer()
    
    try:
        # 初始化服务器
        await server.initialize()
        
        # 启动STDIO服务器
        async with stdio_server() as (read_stream, write_stream):
            await server.server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options={}
            )
            
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # 静默处理错误，避免影响Claude CLI
        pass
    finally:
        try:
            await server.cleanup()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())