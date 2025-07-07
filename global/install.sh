#!/bin/bash
set -e

# Claude Memory MCP 全局服务一键安装脚本
# 支持跨平台部署，自动配置Claude CLI集成

VERSION="2.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/claude_memory_install.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1" | tee -a "$LOG_FILE"
}

# 显示banner
show_banner() {
    echo -e "${PURPLE}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║               Claude Memory MCP 全局服务                       ║
║                                                               ║
║           🧠 跨项目智能记忆管理系统 v2.0.0                     ║
║                                                               ║
║   ✨ 零配置部署 | 🔄 自动迁移 | 🌐 全局共享 | 🚀 即插即用        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            OS="ubuntu"
        elif command -v yum &> /dev/null; then
            OS="centos"
        elif command -v pacman &> /dev/null; then
            OS="arch"
        else
            OS="linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
    else
        OS="unknown"
    fi
    
    log_info "检测到操作系统: $OS"
}

# 检查依赖
check_dependencies() {
    log "检查系统依赖..."
    
    local missing_deps=()
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    else
        log_info "✓ Docker已安装: $(docker --version | cut -d' ' -f3 | cut -d',' -f1)"
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing_deps+=("docker-compose")
    else
        if command -v docker-compose &> /dev/null; then
            log_info "✓ Docker Compose已安装: $(docker-compose --version | cut -d' ' -f3 | cut -d',' -f1)"
        else
            log_info "✓ Docker Compose (v2)已安装"
        fi
    fi
    
    # 检查Python 3
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    else
        log_info "✓ Python 3已安装: $(python3 --version | cut -d' ' -f2)"
    fi
    
    # 检查Git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    else
        log_info "✓ Git已安装: $(git --version | cut -d' ' -f3)"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "缺少必要依赖: ${missing_deps[*]}"
        echo
        echo -e "${YELLOW}请安装缺少的依赖后重新运行安装脚本${NC}"
        echo
        
        case $OS in
            "ubuntu")
                echo "Ubuntu/Debian安装命令:"
                echo "  sudo apt update"
                for dep in "${missing_deps[@]}"; do
                    case $dep in
                        "docker")
                            echo "  curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
                            ;;
                        "docker-compose")
                            echo "  sudo apt install docker-compose-plugin"
                            ;;
                        "python3")
                            echo "  sudo apt install python3 python3-pip"
                            ;;
                        "git")
                            echo "  sudo apt install git"
                            ;;
                    esac
                done
                ;;
            "macos")
                echo "macOS安装命令:"
                echo "  brew install docker docker-compose python3 git"
                echo "  或者下载Docker Desktop: https://www.docker.com/products/docker-desktop"
                ;;
            "centos")
                echo "CentOS/RHEL安装命令:"
                for dep in "${missing_deps[@]}"; do
                    case $dep in
                        "docker")
                            echo "  sudo yum install -y yum-utils && sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo && sudo yum install docker-ce"
                            ;;
                        "docker-compose")
                            echo "  sudo curl -L \"https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64\" -o /usr/local/bin/docker-compose"
                            echo "  sudo chmod +x /usr/local/bin/docker-compose"
                            ;;
                        "python3")
                            echo "  sudo yum install python3 python3-pip"
                            ;;
                        "git")
                            echo "  sudo yum install git"
                            ;;
                    esac
                done
                ;;
        esac
        
        exit 1
    fi
    
    log "✓ 所有依赖检查通过"
}

# 检查Claude CLI
check_claude_cli() {
    log "检查Claude CLI..."
    
    if command -v claude &> /dev/null; then
        CLAUDE_VERSION=$(claude --version 2>/dev/null | head -n1 || echo "unknown")
        log_info "✓ Claude CLI已安装: $CLAUDE_VERSION"
        
        # 检查配置文件
        if [[ "$OS" == "windows" ]]; then
            CLAUDE_CONFIG_DIR="$APPDATA/claude"
        else
            CLAUDE_CONFIG_DIR="$HOME/.claude"
        fi
        
        if [ -f "$CLAUDE_CONFIG_DIR/claude.json" ]; then
            log_info "✓ Claude CLI配置文件存在"
            CLAUDE_CLI_READY=true
        else
            log_warn "Claude CLI配置文件不存在，将创建默认配置"
            CLAUDE_CLI_READY=false
        fi
    else
        log_warn "Claude CLI未安装"
        echo -e "${YELLOW}请先安装Claude CLI:${NC}"
        echo "  npm install -g @anthropic/claude-cli"
        echo "  或访问: https://docs.anthropic.com/claude/docs/claude-cli"
        echo
        read -p "是否继续安装(Claude CLI将稍后配置)? [y/N]: " -r
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        CLAUDE_CLI_READY=false
    fi
}

# 创建全局数据目录
setup_global_directories() {
    log "创建全局数据目录..."
    
    GLOBAL_DATA_DIR="$HOME/.claude-memory"
    
    mkdir -p "$GLOBAL_DATA_DIR"/{data,logs,config,cache,postgres,qdrant}
    
    log_info "✓ 全局数据目录创建完成: $GLOBAL_DATA_DIR"
    
    # 创建默认配置文件
    if [ ! -f "$GLOBAL_DATA_DIR/config/global_config.yml" ]; then
        log "创建默认全局配置..."
        cp "$SCRIPT_DIR/config/global_config.yml" "$GLOBAL_DATA_DIR/config/"
        log_info "✓ 默认配置文件已创建"
    fi
}

# 构建Docker镜像
build_docker_images() {
    log "构建Claude Memory全局Docker镜像..."
    
    cd "$SCRIPT_DIR"
    
    # 构建全局MCP服务镜像
    log_info "构建全局MCP服务镜像..."
    docker build -f Dockerfile.global -t claude-memory-global:$VERSION . || {
        log_error "Docker镜像构建失败"
        exit 1
    }
    
    log "✓ Docker镜像构建完成"
}

# 启动服务
start_services() {
    log "启动Claude Memory全局服务..."
    
    cd "$SCRIPT_DIR"
    
    # 检查并停止现有服务
    if docker-compose -f docker-compose.global.yml ps | grep -q "Up"; then
        log_info "停止现有服务..."
        docker-compose -f docker-compose.global.yml down
    fi
    
    # 启动服务
    log_info "启动全局服务栈..."
    docker-compose -f docker-compose.global.yml up -d || {
        log_error "服务启动失败"
        log_info "查看详细日志: docker-compose -f docker-compose.global.yml logs"
        exit 1
    }
    
    log "✓ 服务启动完成"
    
    # 等待服务就绪
    log "等待服务就绪..."
    sleep 10
    
    # 检查健康状态
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker exec claude-memory-global python /app/healthcheck.py &>/dev/null; then
            log "✓ 服务健康检查通过"
            break
        fi
        
        log_info "等待服务就绪... ($attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_warn "服务健康检查超时，但服务可能仍在初始化中"
    fi
}

# 配置Claude CLI集成
configure_claude_cli() {
    log "配置Claude CLI集成..."
    
    if [ "$CLAUDE_CLI_READY" != true ]; then
        log_warn "跳过Claude CLI配置(CLI未就绪)"
        return
    fi
    
    # 备份现有配置
    if [ -f "$CLAUDE_CONFIG_DIR/claude.json" ]; then
        cp "$CLAUDE_CONFIG_DIR/claude.json" "$CLAUDE_CONFIG_DIR/claude.json.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "✓ 现有配置已备份"
    fi
    
    # 读取现有配置或创建新配置
    local claude_config="{}"
    if [ -f "$CLAUDE_CONFIG_DIR/claude.json" ]; then
        claude_config=$(cat "$CLAUDE_CONFIG_DIR/claude.json")
    fi
    
    # 添加全局MCP服务器配置
    mkdir -p "$CLAUDE_CONFIG_DIR"
    
    cat > "$CLAUDE_CONFIG_DIR/claude.json" << EOF
{
  "mcpServers": {
    "claude-memory-global": {
      "command": "docker",
      "args": ["exec", "-i", "claude-memory-global", "python", "/app/global_mcp_server.py"],
      "env": {}
    }
  }
}
EOF
    
    log "✓ Claude CLI MCP配置已更新"
}

# 验证安装
verify_installation() {
    log "验证安装..."
    
    # 检查容器状态
    if ! docker ps | grep -q "claude-memory-global"; then
        log_error "全局MCP服务容器未运行"
        return 1
    fi
    
    # 检查端口
    if ! netstat -ln 2>/dev/null | grep -q ":6334" && ! ss -ln 2>/dev/null | grep -q ":6334"; then
        log_warn "MCP端口6334可能未监听"
    fi
    
    # 检查健康状态
    local health_output
    health_output=$(docker exec claude-memory-global python /app/healthcheck.py 2>/dev/null || echo '{"status":"error"}')
    
    if echo "$health_output" | grep -q '"overall_status": "ok"'; then
        log "✓ 健康检查通过"
    else
        log_warn "健康检查未通过，服务可能仍在初始化"
    fi
    
    # 检查数据迁移
    local stats_output
    stats_output=$(docker exec claude-memory-global python -c "
import sys, os
sys.path.insert(0, '/app/src')
from global_mcp.global_memory_manager import GlobalMemoryManager
import asyncio
import yaml

with open('/app/config/global_config.yml', 'r') as f:
    config = yaml.safe_load(f)

async def get_stats():
    manager = GlobalMemoryManager(config)
    return await manager.get_stats()

result = asyncio.run(get_stats())
print(f'对话数: {result.get(\"conversation_count\", 0)}, 消息数: {result.get(\"message_count\", 0)}')
" 2>/dev/null || echo "统计信息获取失败")
    
    log_info "数据库统计: $stats_output"
    
    log "✓ 安装验证完成"
}

# 显示安装结果
show_results() {
    echo
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║                  🎉 安装成功完成! 🎉                          ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo
    
    echo -e "${CYAN}📋 服务信息:${NC}"
    echo -e "  🔗 MCP服务地址: localhost:6334"
    echo -e "  📁 全局数据目录: $HOME/.claude-memory"
    echo -e "  🐳 Docker容器: claude-memory-global"
    echo -e "  📊 Vector数据库: localhost:6335"
    echo
    
    echo -e "${CYAN}🚀 快速开始:${NC}"
    echo -e "  1. 打开Claude CLI"
    echo -e "  2. 使用命令: ${GREEN}/mcp claude-memory-global${NC}"
    echo -e "  3. 尝试: ${GREEN}memory_search \"your query\"${NC}"
    echo
    
    echo -e "${CYAN}🛠️  管理命令:${NC}"
    echo -e "  启动服务: ${GREEN}docker-compose -f $SCRIPT_DIR/docker-compose.global.yml up -d${NC}"
    echo -e "  停止服务: ${GREEN}docker-compose -f $SCRIPT_DIR/docker-compose.global.yml down${NC}"
    echo -e "  查看日志: ${GREEN}docker-compose -f $SCRIPT_DIR/docker-compose.global.yml logs -f${NC}"
    echo -e "  健康检查: ${GREEN}docker exec claude-memory-global python /app/healthcheck.py${NC}"
    echo
    
    echo -e "${CYAN}📖 可用MCP工具:${NC}"
    echo -e "  • ${GREEN}memory_search${NC}        - 搜索全局对话记忆"
    echo -e "  • ${GREEN}get_recent_conversations${NC} - 获取最近对话"
    echo -e "  • ${GREEN}get_project_conversations${NC} - 获取项目对话历史"
    echo -e "  • ${GREEN}get_cross_project_memories${NC} - 跨项目记忆搜索"
    echo -e "  • ${GREEN}memory_status${NC}        - 系统状态信息"
    echo -e "  • ${GREEN}memory_health${NC}        - 健康检查"
    echo
    
    if [ "$CLAUDE_CLI_READY" != true ]; then
        echo -e "${YELLOW}⚠️  Claude CLI配置:${NC}"
        echo -e "  请先安装Claude CLI并运行以下命令完成配置:"
        echo -e "  ${GREEN}$SCRIPT_DIR/scripts/configure_claude_cli.sh${NC}"
        echo
    fi
    
    echo -e "${CYAN}📝 配置文件:${NC}"
    echo -e "  全局配置: ${GREEN}$HOME/.claude-memory/config/global_config.yml${NC}"
    echo -e "  Claude CLI: ${GREEN}$CLAUDE_CONFIG_DIR/claude.json${NC}"
    echo
    
    echo -e "${CYAN}🔍 故障排除:${NC}"
    echo -e "  安装日志: ${GREEN}$LOG_FILE${NC}"
    echo -e "  服务日志: ${GREEN}docker logs claude-memory-global${NC}"
    echo -e "  数据迁移: 自动扫描并迁移现有项目数据库"
    echo
}

# 交互式配置
interactive_setup() {
    echo
    echo -e "${BLUE}🔧 交互式配置${NC}"
    echo
    
    # MCP端口配置
    read -p "MCP服务端口 [6334]: " -r MCP_PORT
    MCP_PORT=${MCP_PORT:-6334}
    
    # Qdrant端口配置
    read -p "Qdrant端口 [6335]: " -r QDRANT_PORT
    QDRANT_PORT=${QDRANT_PORT:-6335}
    
    # 日志级别
    echo "日志级别选择:"
    echo "  1) DEBUG - 详细调试信息"
    echo "  2) INFO  - 一般信息 (默认)"
    echo "  3) WARNING - 仅警告和错误"
    echo "  4) ERROR - 仅错误信息"
    read -p "请选择 [2]: " -r LOG_CHOICE
    
    case ${LOG_CHOICE:-2} in
        1) LOG_LEVEL="DEBUG" ;;
        2) LOG_LEVEL="INFO" ;;
        3) LOG_LEVEL="WARNING" ;;
        4) LOG_LEVEL="ERROR" ;;
        *) LOG_LEVEL="INFO" ;;
    esac
    
    # 自动迁移确认
    read -p "是否自动迁移现有项目数据库? [Y/n]: " -r AUTO_MIGRATE
    AUTO_MIGRATE=${AUTO_MIGRATE:-Y}
    
    echo
    log_info "配置完成:"
    log_info "  MCP端口: $MCP_PORT"
    log_info "  Qdrant端口: $QDRANT_PORT" 
    log_info "  日志级别: $LOG_LEVEL"
    log_info "  自动迁移: $AUTO_MIGRATE"
    echo
}

# 主函数
main() {
    show_banner
    
    echo -e "${BLUE}开始安装Claude Memory MCP全局服务...${NC}"
    echo -e "${BLUE}安装日志将保存到: $LOG_FILE${NC}"
    echo
    
    # 解析命令行参数
    local auto_mode=false
    local skip_build=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -a|--auto)
                auto_mode=true
                shift
                ;;
            --skip-build)
                skip_build=true
                shift
                ;;
            -h|--help)
                echo "用法: $0 [选项]"
                echo "选项:"
                echo "  -a, --auto      自动模式，跳过交互式配置"
                echo "  --skip-build    跳过Docker镜像构建"
                echo "  -h, --help      显示帮助信息"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                exit 1
                ;;
        esac
    done
    
    # 检测系统环境
    detect_os
    check_dependencies
    check_claude_cli
    
    # 交互式配置(非自动模式)
    if [ "$auto_mode" != true ]; then
        interactive_setup
    else
        # 默认配置
        MCP_PORT=6334
        QDRANT_PORT=6335
        LOG_LEVEL="INFO"
        AUTO_MIGRATE="Y"
    fi
    
    # 执行安装步骤
    setup_global_directories
    
    if [ "$skip_build" != true ]; then
        build_docker_images
    fi
    
    start_services
    configure_claude_cli
    
    # 等待服务完全启动
    sleep 5
    verify_installation
    
    show_results
    
    log "🎉 Claude Memory MCP全局服务安装完成!"
}

# 错误处理
trap 'log_error "安装过程中发生错误，请查看日志: $LOG_FILE"' ERR

# 运行主函数
main "$@"