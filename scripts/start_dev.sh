#!/bin/bash

# Claude Memory MCP Service - 个人开发环境一键启动脚本
# 适用于 Ubuntu 22.04 个人开发环境

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

# 检查依赖
check_dependencies() {
    print_info "检查系统依赖..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker未安装，请先安装Docker"
        echo "安装命令: curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
        exit 1
    fi
    
    # 检查Docker Compose
    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose未安装，请先安装Docker Compose"
        echo "安装命令: sudo apt-get install docker compose-plugin"
        exit 1
    fi
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python3未安装，请先安装Python3"
        echo "安装命令: sudo apt-get install python3 python3-pip"
        exit 1
    fi
    
    print_success "依赖检查通过"
}

# 检查环境变量
check_env_vars() {
    print_info "检查环境变量配置..."
    
    if [ ! -f ".env" ]; then
        print_error ".env文件不存在，请先复制.env.example为.env"
        exit 1
    fi
    
    # 检查关键API密钥
    if ! grep -q "SILICONFLOW_API_KEY=sk-" .env; then
        print_warning "SILICONFLOW_API_KEY未配置，某些功能可能不可用"
    fi
    
    print_success "环境变量检查完成"
}

# 清理之前的容器
cleanup_containers() {
    print_info "清理之前的容器..."
    
    # 停止并删除开发环境容器
    docker compose -f docker-compose.dev.yml down --volumes --remove-orphans 2>/dev/null || true
    
    # 删除悬挂的镜像
    docker image prune -f &>/dev/null || true
    
    print_success "容器清理完成"
}

# 构建镜像
build_images() {
    print_info "构建应用镜像..."
    
    # 构建开发环境镜像
    docker compose -f docker-compose.dev.yml build --no-cache
    
    print_success "镜像构建完成"
}

# 启动服务
start_services() {
    print_info "启动所有服务..."
    
    # 启动所有服务
    docker compose -f docker-compose.dev.yml up -d
    
    print_success "服务启动完成"
}

# 等待服务就绪
wait_for_services() {
    print_info "等待服务就绪..."
    
    # 等待PostgreSQL
    print_info "等待PostgreSQL启动..."
    timeout=60
    while ! docker compose -f docker-compose.dev.yml exec postgres pg_isready -U claude_memory -d claude_memory &>/dev/null; do
        sleep 2
        timeout=$((timeout - 2))
        if [ $timeout -le 0 ]; then
            print_error "PostgreSQL启动超时"
            exit 1
        fi
    done
    print_success "PostgreSQL就绪"
    
    # 等待Qdrant
    print_info "等待Qdrant启动..."
    timeout=60
    while ! curl -s http://localhost:6333/health &>/dev/null; do
        sleep 2
        timeout=$((timeout - 2))
        if [ $timeout -le 0 ]; then
            print_error "Qdrant启动超时"
            exit 1
        fi
    done
    print_success "Qdrant就绪"
    
    # 等待MCP服务
    print_info "等待MCP服务启动..."
    timeout=90
    while ! curl -s http://localhost:8000/health &>/dev/null; do
        sleep 3
        timeout=$((timeout - 3))
        if [ $timeout -le 0 ]; then
            print_error "MCP服务启动超时"
            docker compose -f docker-compose.dev.yml logs mcp-service
            exit 1
        fi
    done
    print_success "MCP服务就绪"
}

# 初始化数据库
init_database() {
    print_info "初始化数据库..."
    
    # 运行数据库初始化脚本
    docker compose -f docker-compose.dev.yml exec mcp-service python scripts/init_database.py
    
    print_success "数据库初始化完成"
}

# 显示服务状态
show_status() {
    print_info "检查服务状态..."
    
    echo ""
    echo "========================================"
    echo "Claude Memory MCP Service 开发环境"
    echo "========================================"
    echo ""
    
    # 显示容器状态
    docker compose -f docker-compose.dev.yml ps
    
    echo ""
    echo "服务地址："
    echo "- MCP服务器: http://localhost:8000"
    echo "- PostgreSQL: localhost:5432"
    echo "- Qdrant: http://localhost:6333"
    echo ""
    
    # 健康检查
    echo "健康检查："
    if curl -s http://localhost:8000/health | grep -q "ok"; then
        echo "✅ MCP服务健康"
    else
        echo "❌ MCP服务异常"
    fi
    
    if curl -s http://localhost:6333/health &>/dev/null; then
        echo "✅ Qdrant服务健康"
    else
        echo "❌ Qdrant服务异常"
    fi
    
    echo ""
    echo "常用命令："
    echo "- 查看日志: docker compose -f docker-compose.dev.yml logs -f"
    echo "- 停止服务: docker compose -f docker-compose.dev.yml down"
    echo "- 重启服务: docker compose -f docker-compose.dev.yml restart"
    echo "- 进入容器: docker compose -f docker-compose.dev.yml exec mcp-service bash"
    echo ""
    echo "Claude CLI 集成："
    echo "请将以下配置添加到你的Claude CLI配置文件中："
    echo ""
    echo "\"mcp\": {"
    echo "  \"servers\": {"
    echo "    \"claude-memory\": {"
    echo "      \"command\": \"python\","
    echo "      \"args\": [\"-m\", \"src.claude_memory.mcp_server\"],"
    echo "      \"env\": {"
    echo "        \"CLAUDE_MEMORY_MODE\": \"stdio\""
    echo "      }"
    echo "    }"
    echo "  }"
    echo "}"
    echo ""
}

# 主函数
main() {
    echo "========================================"
    echo "Claude Memory MCP Service 开发环境启动"
    echo "========================================"
    echo ""
    
    check_dependencies
    check_env_vars
    cleanup_containers
    build_images
    start_services
    wait_for_services
    init_database
    show_status
    
    print_success "开发环境启动完成！"
    echo ""
    echo "🎉 系统已就绪，可以开始使用Claude Memory MCP服务了！"
}

# 信号处理
trap 'echo ""; print_info "正在停止服务..."; docker compose -f docker-compose.dev.yml down; exit 0' INT TERM

# 运行主函数
main "$@"