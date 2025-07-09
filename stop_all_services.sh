#!/bin/bash
#
# Claude Memory 统一停止脚本
# 
# 功能：
# - 优雅地停止所有运行中的服务
# - 清理进程ID文件
# - 停止Docker容器
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 配置文件
DOCKER_COMPOSE_FILE=${DOCKER_COMPOSE_FILE:-"docker-compose.dev.yml"}

# 打印带颜色的消息
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

echo -e "${BLUE}🛑 Claude Memory 服务停止程序${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""

# 步骤1: 停止 API Server
API_PID_FILE="$PROJECT_ROOT/api_server.pid"
if [ -f "$API_PID_FILE" ]; then
    PID=$(cat "$API_PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        print_status "$YELLOW" "⏹️ 停止 API Server (PID: $PID)..."
        kill -15 "$PID" 2>/dev/null || true
        sleep 2
        # 如果还在运行，强制终止
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -9 "$PID" 2>/dev/null || true
        fi
        print_status "$GREEN" "✅ API Server 已停止"
    else
        print_status "$YELLOW" "⚠️ API Server 进程未找到 (PID: $PID)"
    fi
    rm -f "$API_PID_FILE"
else
    print_status "$YELLOW" "⚠️ API Server PID 文件未找到"
fi

# 步骤2: 停止 MCP Server
MCP_PID_FILE="$PROJECT_ROOT/mcp_server.pid"
if [ -f "$MCP_PID_FILE" ]; then
    PID=$(cat "$MCP_PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        print_status "$YELLOW" "⏹️ 停止 MCP Server (PID: $PID)..."
        kill -15 "$PID" 2>/dev/null || true
        sleep 2
        # 如果还在运行，强制终止
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -9 "$PID" 2>/dev/null || true
        fi
        print_status "$GREEN" "✅ MCP Server 已停止"
    else
        print_status "$YELLOW" "⚠️ MCP Server 进程未找到 (PID: $PID)"
    fi
    rm -f "$MCP_PID_FILE"
else
    print_status "$YELLOW" "⚠️ MCP Server PID 文件未找到"
fi

# 步骤3: 查找并停止所有相关的Python进程
print_status "$BLUE" "🔍 查找其他相关进程..."

# 停止可能的 MCP 进程
for process in "mcp_server" "api_server" "claude_memory"; do
    PIDS=$(pgrep -f "$process" || true)
    if [ -n "$PIDS" ]; then
        print_status "$YELLOW" "⏹️ 停止进程: $process"
        for pid in $PIDS; do
            kill -15 "$pid" 2>/dev/null || true
        done
        sleep 1
    fi
done

# 步骤4: 停止 Docker 服务
if [ -f "$PROJECT_ROOT/$DOCKER_COMPOSE_FILE" ]; then
    print_status "$BLUE" "📦 停止 Docker 服务..."
    docker compose -f "$DOCKER_COMPOSE_FILE" down
    print_status "$GREEN" "✅ Docker 服务已停止"
else
    print_status "$YELLOW" "⚠️ Docker Compose 文件未找到，跳过"
fi

# 步骤5: 清理遗留文件
print_status "$BLUE" "🧹 清理临时文件..."
rm -f "$PROJECT_ROOT"/*.pid
print_status "$GREEN" "✅ 临时文件已清理"

echo ""
print_status "$GREEN" "🎉 所有服务已停止！${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""
print_status "$YELLOW" "💡 提示：使用 ./start_all_services.sh 重新启动所有服务${NC}"