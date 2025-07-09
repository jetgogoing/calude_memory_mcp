#!/bin/bash
#
# Claude Memory 全局服务启动脚本
# 支持从任意位置启动，自动定位项目
#

set -e

# 自动定位脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 设置环境变量
export CLAUDE_MEMORY_HOME="${CLAUDE_MEMORY_HOME:-$PROJECT_ROOT}"
export PYTHONPATH="$CLAUDE_MEMORY_HOME/src:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# 设置统一的项目ID为global
export CLAUDE_MEMORY_PROJECT_ID="global"
export PROJECT__DEFAULT_PROJECT_ID="global"
export PROJECT__PROJECT_ISOLATION_MODE="shared"
export PROJECT__ENABLE_CROSS_PROJECT_SEARCH="true"

# 切换到项目目录
cd "$CLAUDE_MEMORY_HOME"

# 激活虚拟环境（如果存在）
if [ -d "$CLAUDE_MEMORY_HOME/venv" ]; then
    source "$CLAUDE_MEMORY_HOME/venv/bin/activate"
fi

# 执行原始启动脚本
exec "$CLAUDE_MEMORY_HOME/mcp/start.sh" "$@"