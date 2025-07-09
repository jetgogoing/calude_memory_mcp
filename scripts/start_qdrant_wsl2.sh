#!/bin/bash
# WSL2兼容的Qdrant启动脚本
# 解决cgroups和内存管理问题

set -e

QDRANT_PORT=6333
PROJECT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
PID_FILE="/tmp/claude_memory_pids/qdrant.pid"

echo "🚀 启动WSL2兼容的Qdrant服务..."

# 创建必要目录
mkdir -p "/tmp/claude_memory_pids"
mkdir -p "$PROJECT_DIR/data/qdrant"
mkdir -p "$PROJECT_DIR/logs"

# 检查是否已运行
if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    echo "✅ Qdrant已运行 (PID: $(cat "$PID_FILE"))"
    exit 0
fi

# 检查端口是否被占用
if lsof -i:$QDRANT_PORT > /dev/null 2>&1; then
    echo "✅ Qdrant端口已被占用，可能已运行"
    exit 0
fi

# 杀死可能的僵尸进程
pkill -f "qdrant" || true
sleep 1

cd "$PROJECT_DIR"

# 使用Docker启动Qdrant (更稳定的WSL2解决方案)
if command -v docker &> /dev/null; then
    echo "🐳 使用Docker启动Qdrant..."
    
    # 停止现有容器
    docker stop qdrant-claude-memory &>/dev/null || true
    docker rm qdrant-claude-memory &>/dev/null || true
    
    # 启动新容器
    docker run -d \
        --name qdrant-claude-memory \
        -p 6333:6333 \
        -p 6334:6334 \
        -v "$PROJECT_DIR/data/qdrant:/qdrant/storage" \
        qdrant/qdrant:latest
    
    # 等待服务启动
    echo "⏳ 等待Qdrant容器启动..."
    for i in {1..30}; do
        if curl -s http://localhost:6333/ > /dev/null 2>&1; then
            echo "✅ Qdrant Docker容器启动成功!"
            # 保存容器ID作为PID
            docker ps -q -f name=qdrant-claude-memory > "$PID_FILE"
            exit 0
        fi
        sleep 1
    done
    
    echo "❌ Qdrant Docker启动超时"
    exit 1

# 回退：尝试本地二进制文件（禁用cgroups检查）
elif [ -x "./qdrant" ]; then
    echo "📦 使用本地Qdrant二进制文件..."
    
    # 创建简化配置文件
    cat > config/qdrant_simple.yaml << EOF
service:
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334

storage:
  storage_path: ./data/qdrant

telemetry_disabled: true
log_level: INFO

# 禁用可能导致WSL2问题的功能
cluster:
  enabled: false
  
# 简化内存配置
optimizer:
  deleted_threshold: 0.2
  vacuum_min_vector_number: 1000
  
hnsw_config:
  max_indexing_threads: 0
EOF

    # 启动Qdrant
    QDRANT_DISABLE_CGROUPS=1 \
    nohup ./qdrant \
        --config-path config/qdrant_simple.yaml \
        --disable-telemetry \
        > logs/qdrant.log 2>&1 &
    
    QDRANT_PID=$!
    echo $QDRANT_PID > "$PID_FILE"
    
    # 等待服务启动
    echo "⏳ 等待Qdrant启动..."
    for i in {1..30}; do
        if curl -s http://localhost:6333/ > /dev/null 2>&1; then
            echo "✅ Qdrant本地启动成功 (PID: $QDRANT_PID)!"
            echo "🌐 访问地址: http://localhost:6333"
            echo "📊 Web界面: http://localhost:6333/dashboard"
            exit 0
        fi
        sleep 1
    done
    
    echo "❌ Qdrant本地启动超时"
    cat logs/qdrant.log | tail -10
    exit 1

else
    echo "❌ 无法找到Qdrant安装（无Docker，无本地二进制文件）"
    echo "请运行: sudo apt install docker.io"
    exit 1
fi