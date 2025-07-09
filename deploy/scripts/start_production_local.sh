#!/bin/bash

# Claude Memory MCP Service - 本地生产级启动脚本
# 用于在当前 Ubuntu 环境中以生产模式启动服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv-claude-memory"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/claude-memory.pid"

# 打印函数
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# 检查环境
check_environment() {
    print_info "检查环境配置..."
    
    # 检查虚拟环境
    if [ ! -d "$VENV_DIR" ]; then
        print_error "虚拟环境不存在，请先运行 quick_start.sh"
        exit 1
    fi
    
    # 检查配置文件
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        print_error ".env 文件不存在"
        exit 1
    fi
    
    # 加载环境变量
    source "$PROJECT_DIR/.env"
    
    # 检查必需的 API 密钥
    if [ -z "$SILICONFLOW_API_KEY" ]; then
        print_error "SILICONFLOW_API_KEY 未设置"
        exit 1
    fi
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    print_success "环境检查通过"
}

# 检查服务状态
check_services() {
    print_info "检查依赖服务..."
    
    # 检查 PostgreSQL
    if ! pg_isready -h localhost -p ${POSTGRES_PORT:-5432} >/dev/null 2>&1; then
        print_error "PostgreSQL 未运行"
        print_info "尝试启动 PostgreSQL..."
        if command -v docker &> /dev/null; then
            docker-compose up -d postgres
            sleep 5
        else
            exit 1
        fi
    fi
    print_success "PostgreSQL 运行正常"
    
    # 检查 Qdrant
    if ! curl -s http://localhost:${QDRANT_HTTP_PORT:-6333}/ >/dev/null 2>&1; then
        print_error "Qdrant 未运行"
        print_info "尝试启动 Qdrant..."
        if command -v docker &> /dev/null; then
            docker-compose up -d qdrant
            sleep 5
        else
            exit 1
        fi
    fi
    print_success "Qdrant 运行正常"
}

# 停止旧进程
stop_old_process() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            print_info "停止旧进程 (PID: $OLD_PID)..."
            kill "$OLD_PID" 2>/dev/null || true
            sleep 2
            
            # 强制停止
            if ps -p "$OLD_PID" > /dev/null 2>&1; then
                kill -9 "$OLD_PID" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
}

# 优化 Python 运行时
optimize_python() {
    print_info "优化 Python 运行时..."
    
    # Python 优化环境变量
    export PYTHONOPTIMIZE=1
    export PYTHONUNBUFFERED=1
    export PYTHONDONTWRITEBYTECODE=1
    
    # 使用更快的事件循环
    export PYTHONASYNCIODEBUG=0
    
    print_success "Python 优化设置完成"
}

# 启动服务
start_service() {
    print_info "启动 Claude Memory MCP Service..."
    
    cd "$PROJECT_DIR"
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 安装/更新生产依赖
    pip install -q gunicorn uvloop httptools
    
    # 创建 Gunicorn 配置
    cat > "$PROJECT_DIR/gunicorn_config.py" << EOF
import multiprocessing
import os

bind = "127.0.0.1:8000"
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2

accesslog = "$LOG_DIR/access.log"
errorlog = "$LOG_DIR/error.log"
loglevel = "info"

proc_name = 'claude-memory-mcp'
daemon = True
pidfile = "$PID_FILE"
EOF
    
    # 启动 Gunicorn
    PYTHONPATH="$PROJECT_DIR" gunicorn \
        --config "$PROJECT_DIR/gunicorn_config.py" \
        src.claude_memory.mcp_server:app
    
    sleep 3
    
    # 检查是否启动成功
    if [ -f "$PID_FILE" ]; then
        NEW_PID=$(cat "$PID_FILE")
        if ps -p "$NEW_PID" > /dev/null 2>&1; then
            print_success "服务启动成功 (PID: $NEW_PID)"
        else
            print_error "服务启动失败"
            tail -n 50 "$LOG_DIR/error.log"
            exit 1
        fi
    else
        print_error "PID 文件未创建"
        exit 1
    fi
}

# 配置 Nginx（可选）
setup_nginx_proxy() {
    if command -v nginx &> /dev/null; then
        print_info "配置 Nginx 反向代理..."
        
        NGINX_CONF="/tmp/claude-memory-nginx.conf"
        cat > "$NGINX_CONF" << EOF
server {
    listen 8080;
    server_name localhost;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
EOF
        
        print_info "Nginx 配置已生成到: $NGINX_CONF"
        print_info "可以使用以下命令启用："
        print_info "  sudo cp $NGINX_CONF /etc/nginx/sites-available/claude-memory"
        print_info "  sudo ln -s /etc/nginx/sites-available/claude-memory /etc/nginx/sites-enabled/"
        print_info "  sudo nginx -s reload"
    fi
}

# 健康检查
health_check() {
    print_info "执行健康检查..."
    
    # 等待服务完全启动
    sleep 2
    
    # 检查 API 健康状态
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
    
    if [ "$HEALTH_RESPONSE" = "200" ]; then
        print_success "API 健康检查通过"
    else
        print_error "API 健康检查失败 (HTTP $HEALTH_RESPONSE)"
    fi
    
    # 显示进程信息
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        PS_INFO=$(ps -p "$PID" -o pid,vsz,rss,pcpu,pmem,cmd --no-headers)
        print_info "进程信息："
        print_info "$PS_INFO"
    fi
}

# 显示访问信息
show_access_info() {
    echo ""
    echo "========================================"
    echo "Claude Memory MCP Service 已启动"
    echo "========================================"
    echo ""
    echo "访问信息："
    echo "- API 端点: http://localhost:8000"
    echo "- 健康检查: http://localhost:8000/health"
    echo "- 进程 ID: $(cat "$PID_FILE" 2>/dev/null || echo "未知")"
    echo ""
    echo "日志文件："
    echo "- 访问日志: $LOG_DIR/access.log"
    echo "- 错误日志: $LOG_DIR/error.log"
    echo ""
    echo "管理命令："
    echo "- 查看日志: tail -f $LOG_DIR/error.log"
    echo "- 停止服务: kill $(cat "$PID_FILE" 2>/dev/null || echo "PID")"
    echo "- 重启服务: $0"
    echo ""
    echo "性能监控："
    echo "- htop -p $(cat "$PID_FILE" 2>/dev/null || echo "PID")"
    echo "- watch 'curl -s http://localhost:8000/metrics'"
    echo ""
}

# 设置信号处理
trap 'echo "收到中断信号"; stop_old_process; exit 1' INT TERM

# 主函数
main() {
    print_info "启动 Claude Memory MCP Service (生产模式)..."
    echo ""
    
    check_environment
    check_services
    stop_old_process
    optimize_python
    start_service
    setup_nginx_proxy
    health_check
    show_access_info
}

# 运行主函数
main