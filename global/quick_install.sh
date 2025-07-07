#!/bin/bash
set -e

# Claude Memory MCP 全局服务快速安装脚本
# 一键部署，零配置启动

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║          🚀 Claude Memory MCP 快速安装 🚀                     ║
║                                                               ║
║               一键部署 · 零配置 · 即插即用                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${GREEN}正在执行快速安装...${NC}"
echo

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}请先安装Docker:${NC}"
    echo "  macOS: brew install docker 或下载Docker Desktop"
    echo "  Ubuntu: curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
    echo "  其他系统: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✓ Docker已安装"

# 检查Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${YELLOW}请先安装Docker Compose${NC}"
    exit 1
fi

echo "✓ Docker Compose已安装"

# 创建全局数据目录
mkdir -p "$HOME/.claude-memory"/{data,logs,config,cache}
echo "✓ 全局数据目录已创建"

# 复制配置文件
if [ ! -f "$HOME/.claude-memory/config/global_config.yml" ]; then
    cp "$SCRIPT_DIR/config/global_config.yml" "$HOME/.claude-memory/config/"
    echo "✓ 默认配置已复制"
fi

# 构建和启动服务
cd "$SCRIPT_DIR"
echo "🔨 构建Docker镜像..."
docker build -f Dockerfile.global -t claude-memory-global:latest . > /dev/null 2>&1

echo "🚀 启动服务..."
docker-compose -f docker-compose.global.yml down > /dev/null 2>&1 || true
docker-compose -f docker-compose.global.yml up -d

echo "⏳ 等待服务就绪..."
sleep 15

# 健康检查
if docker exec claude-memory-global python /app/healthcheck.py > /dev/null 2>&1; then
    echo "✅ 服务启动成功!"
else
    echo "⚠️  服务可能仍在初始化中..."
fi

echo
echo -e "${GREEN}🎉 快速安装完成!${NC}"
echo
echo -e "${BLUE}下一步:${NC}"
echo "1. 配置Claude CLI: ./scripts/configure_claude_cli.sh"
echo "2. 在Claude CLI中使用: claude mcp call claude-memory-global memory_search"
echo
echo -e "${BLUE}管理命令:${NC}"
echo "启动: docker-compose -f $SCRIPT_DIR/docker-compose.global.yml up -d"
echo "停止: docker-compose -f $SCRIPT_DIR/docker-compose.global.yml down"
echo "日志: docker logs claude-memory-global"
echo