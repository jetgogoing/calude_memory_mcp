#!/usr/bin/env python3
"""
生产级Claude Memory MCP服务器
使用完整架构替代简化版本
"""

import asyncio
import os
import sys
import signal
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 设置环境变量
os.environ.setdefault("PYTHONPATH", str(project_root / "src"))

import structlog
from mcp.server.stdio import stdio_server

# 配置日志
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

async def main():
    """启动生产MCP服务器"""
    
    try:
        logger.info("🚀 Starting Claude Memory MCP Server (Production)")
        
        # 导入完整的MCP服务器
        from claude_memory.mcp_server import ClaudeMemoryMCPServer
        
        # 创建服务器实例
        server = ClaudeMemoryMCPServer()
        
        # 初始化服务器
        await server.initialize()
        logger.info("✅ Server initialized successfully")
        
        # 注册信号处理器
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.get_event_loop().stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动STDIO服务器
        async with stdio_server() as (read_stream, write_stream):
            await server.server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options={}
            )
            
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.info("🔄 Falling back to simple MCP server...")
        
        # 回退到简化版本
        from simple_mcp_server import main as simple_main
        await simple_main()
        
    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
