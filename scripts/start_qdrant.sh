#!/bin/bash
# Qdrant向量数据库启动脚本 (Ubuntu 22.04 原生安装)

set -e

echo "🚀 启动Qdrant向量数据库服务..."

# 配置参数
QDRANT_PORT=${QDRANT_PORT:-6333}
QDRANT_GRPC_PORT=${QDRANT_GRPC_PORT:-6334}
QDRANT_DATA_DIR=${QDRANT_DATA_DIR:-"$(pwd)/data/qdrant"}
QDRANT_CONFIG_DIR=${QDRANT_CONFIG_DIR:-"$(pwd)/config/qdrant"}
QDRANT_LOG_DIR=${QDRANT_LOG_DIR:-"$(pwd)/logs"}

echo "📋 配置信息:"
echo "   HTTP端口: $QDRANT_PORT" 
echo "   gRPC端口: $QDRANT_GRPC_PORT"
echo "   数据目录: $QDRANT_DATA_DIR"
echo "   配置目录: $QDRANT_CONFIG_DIR"
echo "   日志目录: $QDRANT_LOG_DIR"

# 创建必要目录
mkdir -p "$QDRANT_DATA_DIR"
mkdir -p "$QDRANT_CONFIG_DIR" 
mkdir -p "$QDRANT_LOG_DIR"

# 检查Qdrant是否已安装
if ! command -v qdrant &> /dev/null; then
    echo "📦 Qdrant未安装，开始安装..."
    
    # 更新包列表
    sudo apt update
    
    # 安装依赖
    sudo apt install -y curl wget
    
    # 下载并安装Qdrant
    QDRANT_VERSION="1.7.4"
    QDRANT_ARCH="x86_64"
    DOWNLOAD_URL="https://github.com/qdrant/qdrant/releases/download/v${QDRANT_VERSION}/qdrant-${QDRANT_VERSION}-${QDRANT_ARCH}-unknown-linux-gnu.tar.gz"
    
    echo "📥 下载Qdrant v${QDRANT_VERSION}..."
    wget -O /tmp/qdrant.tar.gz "$DOWNLOAD_URL"
    
    echo "📦 解压安装包..."
    tar -xzf /tmp/qdrant.tar.gz -C /tmp/
    
    echo "📂 安装到系统目录..."
    sudo mv /tmp/qdrant /usr/local/bin/
    sudo chmod +x /usr/local/bin/qdrant
    
    # 清理临时文件
    rm -f /tmp/qdrant.tar.gz
    
    echo "✅ Qdrant安装完成!"
fi

# 创建Qdrant配置文件
cat > "$QDRANT_CONFIG_DIR/config.yaml" << EOF
service:
  host: 0.0.0.0
  http_port: $QDRANT_PORT
  grpc_port: $QDRANT_GRPC_PORT
  
storage:
  storage_path: $QDRANT_DATA_DIR
  
log_level: INFO

telemetry_disabled: true

cluster:
  enabled: false

# 性能优化配置
hnsw_config:
  max_indexing_threads: 0
  
segment_config:
  max_segment_size_kb: 200000
EOF

# 检查Qdrant进程是否已运行
if pgrep -f "qdrant" > /dev/null; then
    echo "✅ Qdrant已在运行中"
    echo "🌐 访问地址: http://localhost:$QDRANT_PORT"
    echo "📊 Web界面: http://localhost:$QDRANT_PORT/dashboard"
    exit 0
fi

echo "🔄 启动Qdrant服务..."

# 启动Qdrant服务 (后台运行)
nohup qdrant --config-path "$QDRANT_CONFIG_DIR/config.yaml" > "$QDRANT_LOG_DIR/qdrant.log" 2>&1 &

# 保存PID
QDRANT_PID=$!
echo $QDRANT_PID > "$QDRANT_LOG_DIR/qdrant.pid"

# 等待服务启动
echo "⏳ 等待Qdrant服务启动..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:$QDRANT_PORT/health &> /dev/null; then
        echo "✅ Qdrant服务启动成功!"
        break
    fi
    
    echo "   尝试 $attempt/$max_attempts - 等待服务响应..."
    sleep 2
    ((attempt++))
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ Qdrant服务启动超时"
    echo "请检查日志文件: $QDRANT_LOG_DIR/qdrant.log"
    exit 1
fi

# 显示服务信息
echo ""
echo "🎉 Qdrant向量数据库已成功启动!"
echo "=" * 50
echo "🌐 HTTP API: http://localhost:$QDRANT_PORT"
echo "📊 Web界面: http://localhost:$QDRANT_PORT/dashboard"
echo "⚙️  gRPC端口: $QDRANT_GRPC_PORT"
echo "💾 数据目录: $QDRANT_DATA_DIR"
echo "📄 配置文件: $QDRANT_CONFIG_DIR/config.yaml"
echo "📋 日志文件: $QDRANT_LOG_DIR/qdrant.log"
echo "🔢 进程PID: $QDRANT_PID"
echo ""
echo "📋 常用命令:"
echo "   查看日志: tail -f $QDRANT_LOG_DIR/qdrant.log"
echo "   停止服务: kill \$(cat $QDRANT_LOG_DIR/qdrant.pid)"
echo "   重启服务: bash scripts/start_qdrant.sh"
echo "   检查状态: curl http://localhost:$QDRANT_PORT/health"
echo ""
echo "🔧 下一步: 运行 python scripts/setup_api_keys.py 配置API密钥"