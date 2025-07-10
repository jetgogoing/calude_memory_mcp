#!/bin/bash
#
# Claude Memory 统一启动控制器
# 
# 功能：
# - 统一启动所有服务（PostgreSQL、Qdrant、MCP Server、API Server）
# - 使用环境变量配置，避免硬编码
# - 提供健壮的进程管理和健康检查
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# 加载环境变量
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${BLUE}🔧 加载环境配置...${NC}"
    # 使用 set -a 来自动导出所有变量，更安全的方式
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    echo -e "${GREEN}✅ 环境配置已加载${NC}"
else
    echo -e "${YELLOW}⚠️ 警告: .env 文件未找到，使用默认配置${NC}"
fi

# 配置参数（使用环境变量或默认值）
VENV_NAME=${VENV_NAME:-"venv"}
VENV_DIR="$PROJECT_ROOT/$VENV_NAME"
DOCKER_COMPOSE_FILE=${DOCKER_COMPOSE_FILE:-"docker-compose.dev.yml"}
POSTGRES_PORT=${POSTGRES_PORT:-5433}
QDRANT_PORT=${QDRANT_PORT:-6333}
API_SERVER_PORT=${APP_PORT:-8000}
MCP_SERVER_LOG="$LOG_DIR/mcp_server.log"
API_SERVER_LOG="$LOG_DIR/api_server.log"

# 工具函数：等待端口就绪
wait_for_port() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${BLUE}⏳ 等待 $service_name (端口 $port) 就绪...${NC}"
    while [ $attempt -le $max_attempts ]; do
        if nc -z localhost "$port" 2>/dev/null; then
            echo -e "${GREEN}✅ $service_name 已就绪 (端口 $port)${NC}"
            return 0
        fi
        sleep 1
        ((attempt++))
    done
    
    echo -e "${RED}❌ $service_name 启动超时 (端口 $port)${NC}"
    return 1
}

# 工具函数：检查并终止旧进程
kill_old_process() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        local old_pid=$(cat "$pid_file")
        if ps -p "$old_pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️ 发现 $service_name 旧进程 (PID: $old_pid)，正在终止...${NC}"
            kill -15 "$old_pid" 2>/dev/null || true
            sleep 2
            # 如果还在运行，强制终止
            if ps -p "$old_pid" > /dev/null 2>&1; then
                kill -9 "$old_pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
}

echo -e "${BLUE}🚀 Claude Memory 全自动启动系统${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""

# 步骤1: 启动 Docker 服务（PostgreSQL + Qdrant）
echo -e "${BLUE}📦 启动 Docker 服务...${NC}"
if [ -f "$PROJECT_ROOT/$DOCKER_COMPOSE_FILE" ]; then
    docker compose -f "$DOCKER_COMPOSE_FILE" up -d postgres qdrant
    echo -e "${GREEN}✅ Docker 服务已启动${NC}"
else
    echo -e "${RED}❌ 错误: $DOCKER_COMPOSE_FILE 文件未找到${NC}"
    exit 1
fi

# 步骤2: 等待数据库服务就绪
wait_for_port "$POSTGRES_PORT" "PostgreSQL"
wait_for_port "$QDRANT_PORT" "Qdrant"

# 步骤3: 激活虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ 错误: 虚拟环境未找到 ($VENV_DIR)${NC}"
    echo -e "${YELLOW}请先运行: python3 -m venv $VENV_NAME${NC}"
    exit 1
fi
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✅ Python 虚拟环境已激活${NC}"

# 设置 Python 路径
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

# 步骤4: 初始化数据库（如果需要）
if [ -f "$PROJECT_ROOT/scripts/init_database_tables.py" ]; then
    echo -e "${BLUE}📊 初始化数据库表...${NC}"
    python "$PROJECT_ROOT/scripts/init_database_tables.py" 2>/dev/null || true
fi

# 步骤5: 启动 MCP Server（注意：MCP Server在stdio模式下运行，由Claude CLI管理）
echo -e "${BLUE}🧠 配置 MCP Server...${NC}"
# MCP Server 由 Claude CLI 通过 stdio 管理，这里只需要确保配置正确
echo -e "${GREEN}✅ MCP Server 将由 Claude CLI 自动启动${NC}"

# 步骤6: 启动 API Server
echo -e "${BLUE}🌐 启动 API Server...${NC}"
API_PID_FILE="$PROJECT_ROOT/api_server.pid"
kill_old_process "$API_PID_FILE" "API Server"

# 使用 Python 模块方式启动 API Server，设置 CORS 配置
CORS_ORIGINS='["http://localhost:3000","http://localhost:8000"]' nohup python -u -m claude_memory.api_server > "$API_SERVER_LOG" 2>&1 &
echo $! > "$API_PID_FILE"
echo -e "${GREEN}✅ API Server 已启动 (PID: $(cat $API_PID_FILE))${NC}"

# 等待 API Server 就绪
sleep 3
wait_for_port "$API_SERVER_PORT" "API Server"

# 步骤7: 验证所有服务状态
echo ""
echo -e "${BLUE}🏥 服务健康检查...${NC}"
echo -e "${BLUE}====================================${NC}"

# PostgreSQL
if nc -z localhost "$POSTGRES_PORT" 2>/dev/null; then
    echo -e "${GREEN}✅ PostgreSQL: 运行中 (端口 $POSTGRES_PORT)${NC}"
else
    echo -e "${RED}❌ PostgreSQL: 未运行${NC}"
fi

# Qdrant
if nc -z localhost "$QDRANT_PORT" 2>/dev/null; then
    echo -e "${GREEN}✅ Qdrant: 运行中 (端口 $QDRANT_PORT)${NC}"
else
    echo -e "${RED}❌ Qdrant: 未运行${NC}"
fi

# MCP Server（由Claude CLI管理）
echo -e "${GREEN}✅ MCP Server: 由 Claude CLI 管理${NC}"

# API Server
if curl -s http://localhost:$API_SERVER_PORT/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API Server: 运行中 (端口 $API_SERVER_PORT)${NC}"
else
    echo -e "${RED}❌ API Server: 未运行${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Claude Memory 系统启动完成！${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""
echo -e "${BLUE}📋 快速访问：${NC}"
echo -e "  • API 文档: http://localhost:$API_SERVER_PORT/docs"
echo -e "  • 健康检查: http://localhost:$API_SERVER_PORT/health"
echo ""
echo -e "${BLUE}📝 日志文件：${NC}"
echo -e "  • MCP Server: $MCP_SERVER_LOG"
echo -e "  • API Server: $API_SERVER_LOG"
echo ""
echo -e "${YELLOW}💡 提示：使用 ./stop_all_services.sh 停止所有服务${NC}"