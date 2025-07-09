#!/bin/bash

# Claude Memory MCP Service - 快速启动脚本
# Quick start script for Claude Memory MCP Service

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

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

print_info "Claude Memory MCP Service - 快速启动"
print_info "===================================="

# 1. 检查依赖
print_info "检查系统依赖..."

if ! command_exists python3; then
    print_error "Python3 未安装。请先安装 Python 3.10+"
    exit 1
fi

if ! command_exists docker; then
    print_error "Docker 未安装。请先安装 Docker"
    exit 1
fi

if ! command_exists docker-compose; then
    if ! docker compose version >/dev/null 2>&1; then
        print_error "Docker Compose 未安装"
        exit 1
    fi
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# 2. 创建虚拟环境
if [ ! -d "venv" ] && [ ! -d "venv-claude-memory" ]; then
    print_info "创建 Python 虚拟环境..."
    python3 -m venv venv-claude-memory
fi

# 激活虚拟环境
if [ -d "venv-claude-memory" ]; then
    source venv-claude-memory/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# 3. 安装依赖
print_info "安装 Python 依赖..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 4. 检查环境配置
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

# 5. 检查 API 密钥
source .env
if [ -z "$SILICONFLOW_API_KEY" ]; then
    print_error "SILICONFLOW_API_KEY 未设置！"
    print_error "请编辑 .env 文件添加 API 密钥"
    exit 1
fi

# 6. 启动 Docker 服务
print_info "启动数据库服务..."
$COMPOSE_CMD up -d postgres qdrant

# 等待服务启动
print_info "等待服务就绪..."
sleep 5

# 7. 初始化数据库
print_info "初始化数据库表..."
python scripts/init_database_tables.py

# 8. 运行健康检查
print_info "运行健康检查..."
python << EOF
import asyncio
import httpx
from sqlalchemy import create_engine
import os

async def check_services():
    # 检查 PostgreSQL
    try:
        engine = create_engine(os.getenv('DATABASE_URL'))
        engine.connect()
        print("✓ PostgreSQL 连接正常")
    except Exception as e:
        print(f"✗ PostgreSQL 连接失败: {e}")
        return False
    
    # 检查 Qdrant
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:6333/health")
            if response.status_code == 200:
                print("✓ Qdrant 连接正常")
            else:
                print(f"✗ Qdrant 连接失败: {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Qdrant 连接失败: {e}")
        return False
    
    # 检查 SiliconFlow API
    api_key = os.getenv('SILICONFLOW_API_KEY')
    if api_key and len(api_key) > 10:
        print("✓ SiliconFlow API 密钥已配置")
    else:
        print("✗ SiliconFlow API 密钥未配置")
        return False
    
    return True

success = asyncio.run(check_services())
exit(0 if success else 1)
EOF

if [ $? -ne 0 ]; then
    print_error "服务检查失败，请检查配置"
    exit 1
fi

# 9. 运行快速测试
print_info "运行快速功能测试..."
python tests/performance/test_deepseek_v25_final.py

print_info "========================================"
print_info "✅ Claude Memory MCP Service 启动成功！"
print_info "========================================"
print_info ""
print_info "系统信息："
print_info "  - Mini LLM: SiliconFlow DeepSeek-V2.5"
print_info "  - 延迟: 4-6秒"
print_info "  - 成本: ¥1.33/百万token"
print_info "  - 检索策略: Top-20 → Top-5"
print_info ""
print_info "服务端点："
print_info "  - PostgreSQL: localhost:5433"
print_info "  - Qdrant: http://localhost:6333"
print_info ""
print_info "下一步："
print_info "  1. 启动 MCP 服务: python src/claude_memory/mcp_server.py"
print_info "  2. 配置 Claude 客户端连接"
print_info "  3. 开始使用记忆管理功能"
print_info ""
print_info "查看日志: ./scripts/logs.sh"
print_info "停止服务: ./scripts/stop.sh"