#!/bin/bash
# Qdrant向量数据库停止脚本

set -e

echo "🛑 停止Qdrant向量数据库服务..."

QDRANT_LOG_DIR=${QDRANT_LOG_DIR:-"$(pwd)/logs"}
PID_FILE="$QDRANT_LOG_DIR/qdrant.pid"

# 检查PID文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  PID文件不存在: $PID_FILE"
    echo "尝试查找运行中的Qdrant进程..."
    
    # 查找Qdrant进程
    QDRANT_PIDS=$(pgrep -f "qdrant" || true)
    
    if [ -z "$QDRANT_PIDS" ]; then
        echo "✅ 未发现运行中的Qdrant进程"
        exit 0
    else
        echo "🔍 发现Qdrant进程: $QDRANT_PIDS"
        for pid in $QDRANT_PIDS; do
            echo "   停止进程 $pid..."
            kill $pid || true
        done
        echo "✅ 所有Qdrant进程已停止"
        exit 0
    fi
fi

# 读取PID
QDRANT_PID=$(cat "$PID_FILE")

if [ -z "$QDRANT_PID" ]; then
    echo "❌ PID文件为空"
    exit 1
fi

echo "🔍 检查进程 PID: $QDRANT_PID"

# 检查进程是否存在
if ! kill -0 "$QDRANT_PID" 2>/dev/null; then
    echo "⚠️  进程 $QDRANT_PID 不存在"
    rm -f "$PID_FILE"
    echo "✅ 清理PID文件完成"
    exit 0
fi

echo "🛑 正在停止Qdrant进程 $QDRANT_PID..."

# 优雅停止
kill -TERM "$QDRANT_PID" || true

# 等待进程停止
max_attempts=10
attempt=1

while [ $attempt -le $max_attempts ]; do
    if ! kill -0 "$QDRANT_PID" 2>/dev/null; then
        echo "✅ Qdrant进程已优雅停止"
        rm -f "$PID_FILE"
        exit 0
    fi
    
    echo "   等待进程停止... ($attempt/$max_attempts)"
    sleep 1
    ((attempt++))
done

# 强制停止
echo "⚠️  优雅停止超时，强制终止进程..."
kill -KILL "$QDRANT_PID" || true

# 再次检查
sleep 1
if ! kill -0 "$QDRANT_PID" 2>/dev/null; then
    echo "✅ Qdrant进程已强制停止"
    rm -f "$PID_FILE"
else
    echo "❌ 无法停止Qdrant进程"
    exit 1
fi