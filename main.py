#!/usr/bin/env python3
"""
Claude记忆管理MCP服务 - 主控制模块

统一入口点，支持：
- MCP stdio 模式（默认，用于 Claude Code 集成）
- HTTP API 模式（用于开发调试）
- 自动启动所有依赖服务
- 优雅的错误处理和关闭
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

# 启用asyncio调试模式以获取更详细的错误信息
os.environ['PYTHONASYNCIODEBUG'] = '1'

import click
import structlog
from dotenv import load_dotenv

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from claude_memory.config.settings import get_settings
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.database.session_manager import get_session_manager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)

# 全局服务管理器
service_manager: Optional[ServiceManager] = None
session_manager = None


async def check_dependencies() -> bool:
    """检查必要的依赖服务"""
    settings = get_settings()
    
    # 检查 PostgreSQL
    try:
        import asyncpg
        conn = await asyncpg.connect(
            host=settings.database.host,
            port=settings.database.port,
            database=settings.database.database,
            user=settings.database.user,
            password=settings.database.password,
        )
        await conn.close()
        logger.info("PostgreSQL connection successful")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        logger.error("Please ensure PostgreSQL is running on port 5433")
        return False
    
    # 检查 Qdrant
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.qdrant.qdrant_url}/collections")
            if response.status_code == 200:
                logger.info("Qdrant connection successful")
            else:
                raise Exception(f"Qdrant returned status {response.status_code}")
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        logger.error("Please ensure Qdrant is running on port 6333")
        return False
    
    return True


async def start_stdio_mode():
    """启动 MCP stdio 模式"""
    logger.info("Starting Claude Memory MCP Service in STDIO mode...")
    
    # 导入并运行 MCP 服务器
    from claude_memory.mcp_server import main as mcp_main
    await mcp_main()


async def start_http_mode(host: str = "0.0.0.0", port: int = 8000):
    """启动 HTTP API 模式"""
    logger.info(f"Starting Claude Memory MCP Service in HTTP mode on {host}:{port}...")
    
    # 导入并运行 API 服务器
    import uvicorn
    from claude_memory.api_server import app
    
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def shutdown_handler(sig):
    """优雅关闭处理"""
    logger.info(f"Received signal {sig}, shutting down...")
    
    global service_manager, session_manager
    
    if service_manager:
        await service_manager.stop_service()
        service_manager = None
    
    if session_manager:
        await session_manager.close()
        session_manager = None
    
    logger.info("Shutdown complete")


@click.command()
@click.option(
    '--mode', 
    type=click.Choice(['stdio', 'http'], case_sensitive=False),
    default='stdio',
    help='运行模式：stdio（用于Claude Code）或 http（用于开发调试）',
    envvar='CLAUDE_MEMORY_MODE'
)
@click.option(
    '--host',
    default='0.0.0.0',
    help='HTTP服务器主机地址（仅在http模式下使用）',
    envvar='CLAUDE_MEMORY_HOST'
)
@click.option(
    '--port',
    default=8000,
    type=int,
    help='HTTP服务器端口（仅在http模式下使用）',
    envvar='CLAUDE_MEMORY_PORT'
)
@click.option(
    '--check-deps/--no-check-deps',
    default=True,
    help='启动前检查依赖服务',
    envvar='CLAUDE_MEMORY_CHECK_DEPS'
)
def main(mode: str, host: str, port: int, check_deps: bool):
    """Claude记忆管理MCP服务 - 统一入口"""
    
    # 加载环境变量
    load_dotenv()
    
    # 显示启动信息
    click.echo(f"""
╔═══════════════════════════════════════════════╗
║     Claude Memory MCP Service v1.4.0          ║
║                                               ║
║  Mode: {mode.upper():^10}                          ║
║  Project: {os.getenv('CLAUDE_PROJECT_ID', 'default'):^10}             ║
╚═══════════════════════════════════════════════╝
    """)
    
    # 设置信号处理
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 信号处理
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(
            sig, 
            lambda s, f: asyncio.create_task(shutdown_handler(s))
        )
    
    try:
        # 检查依赖
        if check_deps:
            if not loop.run_until_complete(check_dependencies()):
                click.echo("❌ 依赖服务检查失败，请确保 PostgreSQL 和 Qdrant 正在运行", err=True)
                click.echo("\n可以使用以下命令启动服务：", err=True)
                click.echo("  docker-compose up -d", err=True)
                sys.exit(1)
        
        # 根据模式启动服务
        if mode == 'stdio':
            loop.run_until_complete(start_stdio_mode())
        else:
            loop.run_until_complete(start_http_mode(host, port))
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)
    finally:
        loop.run_until_complete(shutdown_handler(None))
        loop.close()


if __name__ == "__main__":
    main()