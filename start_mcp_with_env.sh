#!/bin/bash
#
# Claude Memory MCP 启动脚本（带环境变量）
# 
# 功能：确保 MCP Server 能够访问 .env 中的环境变量
#

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 加载环境变量
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 设置Python路径
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

# 激活虚拟环境
source venv/bin/activate

# 启动 MCP Server
exec python -m claude_memory.mcp_server "$@"