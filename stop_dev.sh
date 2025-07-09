#!/bin/bash

# Claude Memory MCP Service - 个人开发环境停止脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 打印函数
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 停止服务
stop_services() {
    print_info "停止所有服务..."
    
    # 停止并删除容器
    docker compose -f docker-compose.dev.yml down
    
    print_success "服务停止完成"
}

# 清理资源
cleanup_resources() {
    print_info "清理资源..."
    
    # 删除悬挂的镜像
    docker image prune -f &>/dev/null || true
    
    # 删除未使用的网络
    docker network prune -f &>/dev/null || true
    
    print_success "资源清理完成"
}

# 显示状态
show_status() {
    print_info "服务状态："
    
    # 检查容器状态
    if docker compose -f docker-compose.dev.yml ps | grep -q "Up"; then
        print_warning "仍有容器在运行"
        docker compose -f docker-compose.dev.yml ps
    else
        print_success "所有服务已停止"
    fi
}

# 主函数
main() {
    echo "========================================"
    echo "Claude Memory MCP Service 开发环境停止"
    echo "========================================"
    echo ""
    
    stop_services
    cleanup_resources
    show_status
    
    print_success "开发环境停止完成！"
}

# 运行主函数
main "$@"