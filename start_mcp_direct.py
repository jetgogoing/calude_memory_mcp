#!/usr/bin/env python3
"""
Claude Memory MCP Server - 直接启动脚本
解决路径问题的简化启动器
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 设置环境变量
os.environ["PYTHONPATH"] = str(project_root)
os.environ["DATABASE_URL"] = "postgresql://claude_memory:password@localhost:5433/claude_memory"
os.environ["QDRANT_URL"] = "http://localhost:6333"

# 导入MCP服务器
from claude_memory.mcp_server import main

if __name__ == "__main__":
    print("🚀 Starting Claude Memory MCP Server...")
    print(f"Project root: {project_root}")
    print(f"Python path: {sys.path[0]}")
    print(f"Database URL: {os.environ.get('DATABASE_URL')}")
    print(f"Qdrant URL: {os.environ.get('QDRANT_URL')}")
    
    asyncio.run(main())