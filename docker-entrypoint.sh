#!/bin/bash
set -e

# Claude Memory Docker 入口脚本
# 支持多种运行模式：MCP、API、Both

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 等待服务就绪
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=0
    
    log "Waiting for $service_name on $host:$port..."
    
    while ! nc -z "$host" "$port" 2>/dev/null; do
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            log "ERROR: $service_name not available after $max_attempts attempts"
            return 1
        fi
        log "Waiting for $service_name... ($attempt/$max_attempts)"
        sleep 2
    done
    
    log "$service_name is ready"
    return 0
}

# 初始化数据库
init_database() {
    log "Initializing database..."
    if wait_for_service "${POSTGRES_HOST:-postgres}" "${POSTGRES_PORT:-5432}" "PostgreSQL"; then
        python scripts/init_database_tables.py || {
            log "WARNING: Database initialization failed, but continuing..."
        }
    fi
}

# 启动模式处理
case "${1:-mcp}" in
    "mcp")
        log "Starting Claude Memory MCP Server (stdio mode)..."
        init_database
        exec python -m claude_memory.mcp_server
        ;;
        
    "api")
        log "Starting Claude Memory API Server..."
        init_database
        exec python -m claude_memory.api_server
        ;;
        
    "both")
        log "Starting both MCP and API servers..."
        init_database
        
        # 启动 API 服务器在后台
        python -m claude_memory.api_server &
        API_PID=$!
        
        # 启动 MCP 服务器
        python -m claude_memory.mcp_server &
        MCP_PID=$!
        
        # 等待任一进程退出
        wait -n $API_PID $MCP_PID
        ;;
        
    "shell")
        log "Starting interactive shell..."
        exec /bin/bash
        ;;
        
    *)
        log "Running custom command: $@"
        exec "$@"
        ;;
esac