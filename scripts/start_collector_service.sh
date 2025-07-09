#!/bin/bash
#
# Claude Memory ConversationCollector 服务启动脚本
#

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 设置环境变量
export CLAUDE_MEMORY_HOME="$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# 设置统一的project_id
export CLAUDE_MEMORY_PROJECT_ID="global"
export PROJECT__DEFAULT_PROJECT_ID="global"
export PROJECT__PROJECT_ISOLATION_MODE="shared"
export PROJECT__ENABLE_CROSS_PROJECT_SEARCH="true"

# API Server地址
export CLAUDE_MEMORY_API_URL="${CLAUDE_MEMORY_API_URL:-http://localhost:8000}"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# PID文件
PID_FILE="$PROJECT_ROOT/collector.pid"

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "ConversationCollector is already running (PID: $OLD_PID)"
        exit 1
    else
        echo "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# 激活虚拟环境
if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

echo "Starting ConversationCollector service..."
echo "Project ID: $CLAUDE_MEMORY_PROJECT_ID"
echo "API URL: $CLAUDE_MEMORY_API_URL"
echo "Log file: $LOG_DIR/collector.log"

# 启动服务并保存PID
nohup python "$PROJECT_ROOT/scripts/start_collector.py" \
    > "$LOG_DIR/collector.log" 2>&1 &

PID=$!
echo $PID > "$PID_FILE"

echo "ConversationCollector started with PID: $PID"
echo "Check logs at: $LOG_DIR/collector.log"