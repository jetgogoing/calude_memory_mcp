#!/bin/bash
#
# Claude Memory MCP服务 - 生产环境部署脚本
# 
# 使用方法:
#   ./deploy_production.sh [选项]
#
# 选项:
#   --skip-checks     跳过预部署检查
#   --skip-backup     跳过数据备份
#   --skip-validation 跳过部署后验证
#   --use-docker      使用Docker部署
#   --help            显示帮助信息
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
CONFIG_DIR="$PROJECT_ROOT/config"
LOGS_DIR="$PROJECT_ROOT/logs"
BACKUP_DIR="$PROJECT_ROOT/backups"

# 部署选项
SKIP_CHECKS=false
SKIP_BACKUP=false
SKIP_VALIDATION=false
USE_DOCKER=false

# 时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-checks)
            SKIP_CHECKS=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        --use-docker)
            USE_DOCKER=true
            shift
            ;;
        --help)
            echo "Claude Memory MCP服务 - 生产环境部署脚本"
            echo ""
            echo "使用方法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --skip-checks     跳过预部署检查"
            echo "  --skip-backup     跳过数据备份"
            echo "  --skip-validation 跳过部署后验证"
            echo "  --use-docker      使用Docker部署"
            echo "  --help            显示帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 未知选项: $1${NC}"
            exit 1
            ;;
    esac
done

# 显示部署计划
echo -e "${BLUE}🚀 Claude Memory MCP服务 - 生产环境部署${NC}"
echo "=================================================="
echo -e "部署时间: ${TIMESTAMP}"
echo -e "项目路径: ${PROJECT_ROOT}"
echo -e "部署模式: ${USE_DOCKER:+Docker}${USE_DOCKER:-本地}"
echo -e "部署选项:"
echo -e "  - 预部署检查: ${SKIP_CHECKS:+跳过}${SKIP_CHECKS:-执行}"
echo -e "  - 数据备份: ${SKIP_BACKUP:+跳过}${SKIP_BACKUP:-执行}"
echo -e "  - 部署后验证: ${SKIP_VALIDATION:+跳过}${SKIP_VALIDATION:-执行}"
echo "=================================================="
echo ""

# 确认部署
read -p "确认开始部署？(y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠️ 部署已取消${NC}"
    exit 0
fi

# 创建必要目录
mkdir -p "$LOGS_DIR"
mkdir -p "$BACKUP_DIR"

# 日志文件
DEPLOY_LOG="$LOGS_DIR/deploy_${TIMESTAMP}.log"
exec 1> >(tee -a "$DEPLOY_LOG")
exec 2>&1

echo -e "\n${BLUE}📋 开始部署流程...${NC}"

# 步骤1: 环境准备
echo -e "\n${YELLOW}[1/7] 检查环境配置...${NC}"

# 检查环境文件
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ -f "$PROJECT_ROOT/.env.production" ]; then
        echo -e "${YELLOW}⚠️ 使用 .env.production 作为配置文件${NC}"
        cp "$PROJECT_ROOT/.env.production" "$PROJECT_ROOT/.env"
    else
        echo -e "${RED}❌ 未找到环境配置文件，请先创建 .env 或 .env.production${NC}"
        exit 1
    fi
fi

# 加载环境变量
set -a
source "$PROJECT_ROOT/.env"
set +a

echo -e "${GREEN}✅ 环境配置已加载${NC}"

# 步骤2: 预部署检查
if [ "$SKIP_CHECKS" = false ]; then
    echo -e "\n${YELLOW}[2/7] 执行预部署检查...${NC}"
    
    if python3 "$SCRIPTS_DIR/pre_deploy_check.py"; then
        echo -e "${GREEN}✅ 预部署检查通过${NC}"
    else
        echo -e "${RED}❌ 预部署检查失败，请修复问题后重试${NC}"
        exit 1
    fi
else
    echo -e "\n${YELLOW}[2/7] 跳过预部署检查${NC}"
fi

# 步骤3: 数据备份
if [ "$SKIP_BACKUP" = false ]; then
    echo -e "\n${YELLOW}[3/7] 备份现有数据...${NC}"
    
    # 备份PostgreSQL
    if command -v pg_dump &> /dev/null; then
        BACKUP_FILE="$BACKUP_DIR/claude_memory_${TIMESTAMP}.sql"
        echo -e "  📦 备份PostgreSQL数据库..."
        
        # 解析数据库URL
        DB_HOST=$(echo $DATABASE_URL | sed -E 's/.*@([^:]+):.*/\1/')
        DB_PORT=$(echo $DATABASE_URL | sed -E 's/.*:([0-9]+)\/.*/\1/')
        DB_NAME=$(echo $DATABASE_URL | sed -E 's/.*\/([^?]+).*/\1/')
        DB_USER=$(echo $DATABASE_URL | sed -E 's/.*\/\/([^:]+):.*/\1/')
        
        PGPASSWORD=$(echo $DATABASE_URL | sed -E 's/.*:\/\/[^:]+:([^@]+)@.*/\1/') \
        pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ 数据库备份完成: $BACKUP_FILE${NC}"
        else
            echo -e "${YELLOW}  ⚠️ 数据库备份失败，继续部署${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠️ pg_dump未安装，跳过数据库备份${NC}"
    fi
    
    # 备份配置文件
    echo -e "  📦 备份配置文件..."
    tar -czf "$BACKUP_DIR/config_${TIMESTAMP}.tar.gz" -C "$PROJECT_ROOT" .env config/
    echo -e "${GREEN}  ✅ 配置文件备份完成${NC}"
else
    echo -e "\n${YELLOW}[3/7] 跳过数据备份${NC}"
fi

# 步骤4: 停止现有服务
echo -e "\n${YELLOW}[4/7] 停止现有服务...${NC}"

if [ "$USE_DOCKER" = true ]; then
    # Docker模式
    if docker-compose -f "$PROJECT_ROOT/docker-compose.yml" ps -q | grep -q .; then
        echo -e "  🛑 停止Docker容器..."
        docker-compose -f "$PROJECT_ROOT/docker-compose.yml" down
        echo -e "${GREEN}  ✅ Docker容器已停止${NC}"
    else
        echo -e "  ℹ️ 没有运行中的Docker容器"
    fi
else
    # 本地模式
    # 停止MCP服务
    if pgrep -f "mcp_server.py" > /dev/null; then
        echo -e "  🛑 停止MCP服务..."
        pkill -f "mcp_server.py" || true
        sleep 2
        echo -e "${GREEN}  ✅ MCP服务已停止${NC}"
    fi
    
    # 停止API服务
    if pgrep -f "api_server.py" > /dev/null; then
        echo -e "  🛑 停止API服务..."
        pkill -f "api_server.py" || true
        sleep 2
        echo -e "${GREEN}  ✅ API服务已停止${NC}"
    fi
fi

# 步骤5: 更新代码和依赖
echo -e "\n${YELLOW}[5/7] 更新代码和依赖...${NC}"

# 安装/更新Python依赖
echo -e "  📦 更新Python依赖..."
pip install -r "$PROJECT_ROOT/requirements.txt" --upgrade

echo -e "${GREEN}  ✅ 依赖更新完成${NC}"

# 数据库迁移
echo -e "  🗄️ 执行数据库迁移..."
python3 "$SCRIPTS_DIR/init_database_tables.py"
echo -e "${GREEN}  ✅ 数据库迁移完成${NC}"

# 步骤6: 启动服务
echo -e "\n${YELLOW}[6/7] 启动服务...${NC}"

if [ "$USE_DOCKER" = true ]; then
    # Docker模式
    echo -e "  🐳 使用Docker Compose启动服务..."
    
    # 构建镜像
    docker-compose -f "$PROJECT_ROOT/docker-compose.yml" build
    
    # 启动服务
    docker-compose -f "$PROJECT_ROOT/docker-compose.yml" up -d
    
    # 等待服务就绪
    echo -e "  ⏳ 等待服务就绪..."
    sleep 10
    
    # 检查服务状态
    if docker-compose -f "$PROJECT_ROOT/docker-compose.yml" ps | grep -q "Up"; then
        echo -e "${GREEN}  ✅ Docker服务启动成功${NC}"
    else
        echo -e "${RED}  ❌ Docker服务启动失败${NC}"
        docker-compose -f "$PROJECT_ROOT/docker-compose.yml" logs --tail=50
        exit 1
    fi
else
    # 本地模式
    echo -e "  🚀 启动本地服务..."
    
    # 启动MCP服务
    echo -e "  📡 启动MCP服务..."
    nohup python3 "$PROJECT_ROOT/src/claude_memory/mcp_server.py" > "$LOGS_DIR/mcp_server.log" 2>&1 &
    MCP_PID=$!
    echo $MCP_PID > "$PROJECT_ROOT/mcp_server.pid"
    
    # 启动API服务
    echo -e "  🌐 启动API服务..."
    nohup python3 "$PROJECT_ROOT/src/claude_memory/api_server.py" > "$LOGS_DIR/api_server.log" 2>&1 &
    API_PID=$!
    echo $API_PID > "$PROJECT_ROOT/api_server.pid"
    
    # 等待服务就绪
    echo -e "  ⏳ 等待服务就绪..."
    sleep 5
    
    # 检查进程是否存在
    if ps -p $MCP_PID > /dev/null && ps -p $API_PID > /dev/null; then
        echo -e "${GREEN}  ✅ 服务启动成功${NC}"
        echo -e "    MCP服务 PID: $MCP_PID"
        echo -e "    API服务 PID: $API_PID"
    else
        echo -e "${RED}  ❌ 服务启动失败${NC}"
        tail -n 50 "$LOGS_DIR/mcp_server.log" "$LOGS_DIR/api_server.log"
        exit 1
    fi
fi

# 步骤7: 部署后验证
if [ "$SKIP_VALIDATION" = false ]; then
    echo -e "\n${YELLOW}[7/7] 执行部署后验证...${NC}"
    
    # 等待服务完全启动
    sleep 5
    
    if python3 "$SCRIPTS_DIR/post_deploy_validation.py"; then
        echo -e "${GREEN}✅ 部署后验证通过${NC}"
    else
        echo -e "${RED}❌ 部署后验证失败，请检查服务状态${NC}"
        # 不退出，因为服务可能已经启动
    fi
else
    echo -e "\n${YELLOW}[7/7] 跳过部署后验证${NC}"
fi

# 部署完成
echo -e "\n${GREEN}🎉 部署完成！${NC}"
echo "=================================================="
echo -e "部署时间: $(date +"%Y-%m-%d %H:%M:%S")"
echo -e "部署日志: $DEPLOY_LOG"

if [ "$USE_DOCKER" = true ]; then
    echo -e "\nDocker服务状态:"
    docker-compose -f "$PROJECT_ROOT/docker-compose.yml" ps
    echo -e "\n查看日志: docker-compose -f $PROJECT_ROOT/docker-compose.yml logs -f"
else
    echo -e "\n服务访问地址:"
    echo -e "  - MCP服务: http://localhost:${PORT:-8000}"
    echo -e "  - 健康检查: http://localhost:${PORT:-8000}/health"
    echo -e "  - Prometheus指标: http://localhost:${PORT:-8000}/metrics"
    echo -e "\n查看日志:"
    echo -e "  - MCP服务: tail -f $LOGS_DIR/mcp_server.log"
    echo -e "  - API服务: tail -f $LOGS_DIR/api_server.log"
fi

echo -e "\n${BLUE}提示:${NC}"
echo -e "  - 使用 '$SCRIPTS_DIR/monitoring_control.sh status' 检查监控状态"
echo -e "  - 使用 '$SCRIPTS_DIR/monitoring_control.sh start' 启动监控服务"
echo "=================================================="

# 创建部署成功标记
touch "$PROJECT_ROOT/.last_deploy_${TIMESTAMP}"

exit 0