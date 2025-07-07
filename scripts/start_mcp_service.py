#!/usr/bin/env python3
"""
启动Claude Memory MCP服务
用于与Claude CLI集成
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加src到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from claude_memory.mcp_server import ClaudeMemoryMCPServer

async def main():
    """启动MCP服务"""
    print("🚀 启动Claude Memory MCP服务...")
    
    # 创建MCP服务器实例
    mcp_server = ClaudeMemoryMCPServer()
    
    try:
        # 初始化服务器
        await mcp_server.initialize()
        
        print("✅ Claude Memory MCP服务已启动")
        print("📡 等待Claude CLI连接...")
        
        # 运行MCP服务器
        async with mcp_server.server.run_server() as streams:
            await mcp_server.server.run(
                read_stream=streams[0],
                write_stream=streams[1],
                initialization_options={}
            )
            
    except KeyboardInterrupt:
        print("\n🛑 接收到中断信号，正在停止服务...")
    except Exception as e:
        print(f"\n❌ MCP服务启动失败: {e}")
        return 1
    finally:
        await mcp_server.cleanup()
        print("🔄 MCP服务已停止")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"💥 启动失败: {e}")
        sys.exit(1)