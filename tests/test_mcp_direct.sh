#!/bin/bash
# 测试 MCP Server 直接启动

# 加载环境变量
source /home/jetgogoing/claude_memory/.env
export PYTHONPATH="/home/jetgogoing/claude_memory/src"

# 激活虚拟环境
source /home/jetgogoing/claude_memory/venv/bin/activate

echo "测试 MCP Server 直接启动..."
echo "按 Ctrl+C 退出"
echo ""

# 启动 MCP Server
python -m claude_memory.mcp_server