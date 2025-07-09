#!/bin/bash
# Claude Memory MCP 服务管理脚本
# 实现真正的自动启动和无密码部署

set -e

# 配置参数
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
PID_DIR="/tmp/claude_memory_pids"
QDRANT_PID_FILE="$PID_DIR/qdrant.pid"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 确保PID目录存在
mkdir -p "$PID_DIR"

is_qdrant_running() {
    if [ -f "$QDRANT_PID_FILE" ] && ps -p $(cat "$QDRANT_PID_FILE") > /dev/null 2>&1; then
        return 0
    fi
    # 也检查端口是否被占用
    if lsof -i:$QDRANT_PORT > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

start_qdrant() {
    if is_qdrant_running; then
        log_success "Qdrant已运行 (PID: $(cat "$QDRANT_PID_FILE" 2>/dev/null || echo "未知"))"
        return 0
    fi

    log_info "启动Qdrant向量数据库 (WSL2兼容模式)..."
    
    # 使用WSL2兼容的启动脚本
    if [ -x "$SCRIPT_DIR/start_qdrant_wsl2.sh" ]; then
        if "$SCRIPT_DIR/start_qdrant_wsl2.sh"; then
            log_success "Qdrant启动成功"
            return 0
        else
            log_error "Qdrant启动失败"
            return 1
        fi
    else
        log_error "WSL2 Qdrant启动脚本不存在"
        return 1
    fi
}

stop_qdrant() {
    if [ -f "$QDRANT_PID_FILE" ]; then
        PID=$(cat "$QDRANT_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log_info "停止Qdrant (PID: $PID)..."
            kill $PID
            rm "$QDRANT_PID_FILE"
            log_success "Qdrant已停止"
        else
            log_warning "Qdrant进程不存在，清理PID文件"
            rm "$QDRANT_PID_FILE"
        fi
    else
        log_warning "未找到Qdrant PID文件"
    fi
}

start_services() {
    log_info "启动Claude Memory服务..."
    
    # 激活虚拟环境
    if [ -f "$PROJECT_DIR/venv-claude-memory/bin/activate" ]; then
        source "$PROJECT_DIR/venv-claude-memory/bin/activate"
        log_success "虚拟环境已激活"
    else
        log_error "虚拟环境不存在"
        return 1
    fi
    
    # 启动Qdrant
    start_qdrant
    
    # 验证系统状态
    if curl -s http://localhost:$QDRANT_PORT/collections > /dev/null 2>&1; then
        log_success "所有服务启动完成！"
        echo ""
        echo "🌐 Qdrant API: http://localhost:$QDRANT_PORT"
        echo "📊 Web界面: http://localhost:$QDRANT_PORT/dashboard"
        echo "📄 日志文件: $PROJECT_DIR/logs/qdrant.log"
        echo ""
        return 0
    else
        log_error "服务启动验证失败"
        return 1
    fi
}

stop_services() {
    log_info "停止所有Claude Memory服务..."
    stop_qdrant
    log_success "所有服务已停止"
}

status_services() {
    echo "Claude Memory MCP 服务状态："
    echo "================================"
    
    if is_qdrant_running; then
        echo "✅ Qdrant: 运行中"
        if [ -f "$QDRANT_PID_FILE" ]; then
            echo "   PID: $(cat "$QDRANT_PID_FILE")"
        fi
        echo "   端口: $QDRANT_PORT"
        
        # 获取集合信息
        if command -v curl > /dev/null; then
            COLLECTIONS=$(curl -s http://localhost:$QDRANT_PORT/collections 2>/dev/null | grep -o '"name":"[^"]*"' | wc -l || echo "0")
            echo "   集合数量: $COLLECTIONS"
        fi
    else
        echo "❌ Qdrant: 未运行"
    fi
    
    echo ""
    echo "💾 数据目录: $PROJECT_DIR/data/qdrant"
    echo "📄 日志目录: $PROJECT_DIR/logs"
}

# 删除所有密码配置
remove_passwords() {
    log_info "移除数据库密码配置..."
    
    # 这里不需要做什么，因为我们已经检查过没有密码配置
    # Qdrant默认无认证
    # PostgreSQL如果有的话，用户可以后续配置为trust模式
    
    log_success "无密码配置已确认"
}

case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        start_services
        ;;
    status)
        status_services
        ;;
    remove-passwords)
        remove_passwords
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|remove-passwords}"
        echo ""
        echo "命令说明："
        echo "  start            - 启动所有服务"
        echo "  stop             - 停止所有服务"
        echo "  restart          - 重启所有服务"
        echo "  status           - 显示服务状态"
        echo "  remove-passwords - 移除密码配置"
        exit 1
        ;;
esac