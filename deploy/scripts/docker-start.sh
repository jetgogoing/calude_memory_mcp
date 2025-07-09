#!/bin/bash

# Claude Memory MCP Service - Docker Compose 启动脚本
# Start all services using Docker Compose

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 检查 Docker
if ! command -v docker >/dev/null 2>&1; then
    print_error "Docker 未安装。请先安装 Docker"
    exit 1
fi

# 检查 docker-compose
if ! command -v docker-compose >/dev/null 2>&1; then
    if ! docker compose version >/dev/null 2>&1; then
        print_error "Docker Compose 未安装"
        exit 1
    fi
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

print_info "Claude Memory MCP Service - Docker Compose 部署"
print_info "==========================================="

# 检查 .env 文件
if [ ! -f .env ]; then
    print_warning ".env 文件不存在，从模板创建..."
    cp .env.example .env
    print_warning "请编辑 .env 文件，添加必要的 API 密钥："
    print_warning "  - SILICONFLOW_API_KEY (必需)"
    print_warning "  - OPENROUTER_API_KEY (可选)"
    print_warning "  - GEMINI_API_KEY (可选)"
    echo ""
    read -p "按 Enter 继续，或 Ctrl+C 退出编辑 .env 文件..."
fi

# 检查 API 密钥
source .env
if [ -z "$SILICONFLOW_API_KEY" ]; then
    print_error "SILICONFLOW_API_KEY 未设置！"
    print_error "请编辑 .env 文件添加 API 密钥"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 构建镜像
print_info "构建 Docker 镜像..."
$COMPOSE_CMD build

# 启动服务
print_info "启动所有服务..."
$COMPOSE_CMD up -d

# 等待服务就绪
print_info "等待服务就绪..."
sleep 10

# 健康检查
print_info "执行健康检查..."
$COMPOSE_CMD ps

# 检查服务状态
print_info "检查服务健康状态..."
for service in postgres qdrant mcp-service; do
    if $COMPOSE_CMD ps | grep -q "${service}.*healthy"; then
        print_info "✓ ${service} 服务健康"
    else
        print_warning "⚠ ${service} 服务状态异常"
    fi
done

# 查看 MCP 服务日志
print_info "MCP 服务最近日志："
$COMPOSE_CMD logs --tail=20 mcp-service

print_info "========================================"
print_info "✅ Docker Compose 部署完成！"
print_info "========================================"
print_info ""
print_info "服务状态："
$COMPOSE_CMD ps
print_info ""
print_info "服务端点："
print_info "  - MCP Service: http://localhost:${MCP_PORT:-8000}"
print_info "  - PostgreSQL: localhost:${POSTGRES_PORT:-5432}"
print_info "  - Qdrant: http://localhost:${QDRANT_HTTP_PORT:-6333}"
print_info ""
print_info "管理命令："
print_info "  - 查看日志: docker-compose logs -f"
print_info "  - 停止服务: docker-compose down"
print_info "  - 重启服务: docker-compose restart"
print_info "  - 查看状态: docker-compose ps"