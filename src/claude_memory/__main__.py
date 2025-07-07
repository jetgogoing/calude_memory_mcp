"""
Claude记忆管理MCP服务 - 命令行入口

支持多种运行模式：MCP服务器、独立服务、开发模式等。
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import structlog

from claude_memory.mcp_server import main as mcp_main
from claude_memory.config.settings import get_settings


def setup_logging(log_level: str = "INFO", json_logs: bool = True) -> None:
    """
    设置日志配置
    
    Args:
        log_level: 日志级别
        json_logs: 是否使用JSON格式
    """
    level = getattr(logging, log_level.upper())
    
    if json_logs:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer()
        ]
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logging.basicConfig(
        level=level,
        format="%(message)s" if json_logs else "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def create_parser() -> argparse.ArgumentParser:
    """
    创建命令行参数解析器
    
    Returns:
        argparse.ArgumentParser: 参数解析器
    """
    parser = argparse.ArgumentParser(
        prog="claude-memory-mcp",
        description="Claude记忆管理MCP服务 - 企业级RAG解决方案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 启动MCP服务器（默认模式）
  python -m claude_memory

  # 指定配置文件启动
  python -m claude_memory --config /path/to/config.yaml

  # 开发模式启动（详细日志）
  python -m claude_memory --mode dev --log-level DEBUG

  # 检查配置
  python -m claude_memory --mode config-check

环境变量:
  CLAUDE_MEMORY_CONFIG_PATH: 配置文件路径
  CLAUDE_MEMORY_LOG_LEVEL: 日志级别 (DEBUG, INFO, WARNING, ERROR)
  CLAUDE_MEMORY_JSON_LOGS: 是否使用JSON日志格式 (true/false)
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["mcp", "standalone", "dev", "config-check", "version"],
        default="mcp",
        help="运行模式 (默认: mcp)"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        help="配置文件路径"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)"
    )
    
    parser.add_argument(
        "--json-logs",
        action="store_true",
        default=True,
        help="使用JSON格式日志 (默认: true)"
    )
    
    parser.add_argument(
        "--no-json-logs",
        action="store_false",
        dest="json_logs",
        help="使用普通格式日志"
    )
    
    parser.add_argument(
        "--host",
        default="localhost",
        help="服务监听地址 (standalone模式)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="服务监听端口 (standalone模式)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="工作进程数量 (standalone模式)"
    )
    
    return parser


async def run_mcp_mode() -> None:
    """
    运行MCP服务器模式
    """
    logger = structlog.get_logger(__name__)
    logger.info("Starting Claude Memory MCP Server...")
    await mcp_main()


async def run_standalone_mode(host: str, port: int, workers: int) -> None:
    """
    运行独立服务模式
    
    Args:
        host: 监听地址
        port: 监听端口
        workers: 工作进程数
    """
    logger = structlog.get_logger(__name__)
    logger.info("Starting Claude Memory Standalone Server...")
    
    try:
        import uvicorn
        from claude_memory.api.app import create_app
        
        app = await create_app()
        
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            workers=workers,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    except ImportError:
        logger.error("Standalone mode requires uvicorn and fastapi. Install with: pip install 'claude-memory[api]'")
        sys.exit(1)
    except Exception as e:
        logger.error("Standalone server failed", error=str(e))
        sys.exit(1)


def run_config_check() -> None:
    """
    检查配置
    """
    logger = structlog.get_logger(__name__)
    logger.info("Checking configuration...")
    
    try:
        settings = get_settings()
        
        print("\\n=== Claude Memory MCP 配置检查 ===\\n")
        
        # 基本配置
        print(f"服务版本: {settings.service.version}")
        print(f"服务名称: {settings.service.name}")
        print(f"调试模式: {settings.service.debug}")
        
        # 数据库配置
        print(f"\\n数据库URL: {settings.database.database_url}")
        print(f"连接池大小: {settings.database.pool_size}")
        print(f"最大溢出: {settings.database.max_overflow}")
        
        # Qdrant配置
        print(f"\\nQdrant URL: {settings.qdrant.qdrant_url}")
        print(f"向量维度: {settings.qdrant.vector_size}")
        print(f"集合名称: {settings.qdrant.collection_name}")
        
        # 模型配置
        print(f"\\n嵌入模型: {settings.models.default_embedding_model}")
        print(f"轻量模型: {settings.models.default_light_model}")
        print(f"重型模型: {settings.models.default_heavy_model}")
        
        # 记忆配置
        print(f"\\nQuick记忆TTL: {settings.memory.quick_mu_ttl_hours}小时")
        print(f"质量阈值: {settings.memory.quality_threshold}")
        print(f"最大记忆单元: {settings.memory.max_memory_units}")
        
        # 性能配置
        print(f"\\n批处理大小: {settings.performance.batch_size}")
        print(f"最大并发请求: {settings.performance.max_concurrent_requests}")
        print(f"请求超时: {settings.performance.request_timeout_seconds}秒")
        
        print("\\n✅ 配置检查完成")
        
    except Exception as e:
        logger.error("Configuration check failed", error=str(e))
        print(f"\\n❌ 配置检查失败: {str(e)}")
        sys.exit(1)


def show_version() -> None:
    """
    显示版本信息
    """
    from claude_memory import __version__, __title__, __description__
    
    print(f"\\n{__title__}")
    print(f"版本: {__version__}")
    print(f"描述: {__description__}")
    print("\\n功能特性:")
    print("  ✓ 自动对话采集与解析")
    print("  ✓ 智能语义压缩与记忆单元生成")
    print("  ✓ 高性能向量语义检索")
    print("  ✓ 动态上下文构建与注入")
    print("  ✓ 多模型协作与成本控制")
    print("  ✓ 企业级监控与管理")
    print("\\n技术栈:")
    print("  • Python 3.11+")
    print("  • SQLAlchemy + PostgreSQL/SQLite")
    print("  • Qdrant 向量数据库")
    print("  • Pydantic v2 数据验证")
    print("  • Structlog 结构化日志")
    print("  • AsyncIO 异步编程")
    print("\\n支持:")
    print("  📧 Email: support@example.com")
    print("  📚 文档: https://docs.example.com")
    print("  🐛 Issues: https://github.com/example/claude-memory/issues")


async def main() -> None:
    """
    主入口函数
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.log_level, args.json_logs)
    
    logger = structlog.get_logger(__name__)
    
    try:
        if args.mode == "version":
            show_version()
            return
        
        if args.mode == "config-check":
            run_config_check()
            return
        
        logger.info(
            "Starting Claude Memory MCP Service",
            mode=args.mode,
            log_level=args.log_level,
            json_logs=args.json_logs
        )
        
        if args.mode == "mcp":
            await run_mcp_mode()
        
        elif args.mode == "standalone":
            await run_standalone_mode(args.host, args.port, args.workers)
        
        elif args.mode == "dev":
            # 开发模式：启动MCP服务器并开启所有调试功能
            import os
            os.environ["CLAUDE_MEMORY_DEBUG"] = "true"
            await run_mcp_mode()
        
        else:
            logger.error(f"Unknown mode: {args.mode}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error("Application failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())