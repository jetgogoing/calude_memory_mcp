#!/bin/bash
#
# Claude Memory ConversationCollector 服务停止脚本
#

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# PID文件
PID_FILE="$PROJECT_ROOT/collector.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "ConversationCollector is not running (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping ConversationCollector (PID: $PID)..."
    kill "$PID"
    
    # 等待进程结束
    for i in {1..10}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "ConversationCollector stopped successfully"
            rm "$PID_FILE"
            exit 0
        fi
        sleep 1
    done
    
    # 如果进程还在运行，强制终止
    echo "Force killing ConversationCollector..."
    kill -9 "$PID"
    rm "$PID_FILE"
    echo "ConversationCollector force killed"
else
    echo "ConversationCollector is not running (PID $PID not found)"
    rm "$PID_FILE"
fi