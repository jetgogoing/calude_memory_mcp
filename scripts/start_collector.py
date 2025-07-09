#!/usr/bin/env python3
"""
Claude记忆管理 - ConversationCollector 启动脚本

自动收集Claude CLI对话并发送到API Server
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_memory.collectors.conversation_collector import ConversationCollector
from claude_memory.config.settings import get_settings
import structlog

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
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def main():
    """主函数"""
    logger.info("Starting ConversationCollector...")
    
    # 获取配置
    settings = get_settings()
    
    # 使用统一的project_id
    project_id = os.getenv("CLAUDE_MEMORY_PROJECT_ID", settings.project.default_project_id)
    logger.info(f"Using project_id: {project_id}")
    
    # 创建Collector实例
    collector = ConversationCollector(project_id=project_id)
    
    # 启动收集服务
    try:
        await collector.start_collection()
    except KeyboardInterrupt:
        logger.info("Shutting down ConversationCollector...")
        await collector.stop_collection()
    except Exception as e:
        logger.error("ConversationCollector failed", error=str(e))
        await collector.stop_collection()
        sys.exit(1)


if __name__ == "__main__":
    # 设置环境变量
    os.environ.setdefault("CLAUDE_MEMORY_PROJECT_ID", "global")
    
    # 运行主函数
    asyncio.run(main())