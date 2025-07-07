#!/bin/bash
set -e

# Claude Memory MCP 全局服务 macOS 专用安装脚本
# 优化macOS环境，支持Homebrew和系统特性

VERSION="2.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/claude_memory_install_macos.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

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

# 显示macOS专用banner
show_macos_banner() {
    echo -e "${PURPLE}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║          🍎 Claude Memory MCP for macOS 🍎                    ║
║                                                               ║
║        专为macOS优化的跨项目智能记忆管理系统                   ║
║                                                               ║
║     ✨ Homebrew集成 | 🔄 自动配置 | 🚀 原生体验                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# 检查macOS版本
check_macos_version() {
    log "检查macOS版本..."
    
    MACOS_VERSION=$(sw_vers -productVersion)
    MACOS_MAJOR=$(echo $MACOS_VERSION | cut -d. -f1)
    MACOS_MINOR=$(echo $MACOS_VERSION | cut -d. -f2)
    
    log_info "macOS版本: $MACOS_VERSION"
    
    # 检查版本兼容性 (macOS 10.15+)
    if [[ $MACOS_MAJOR -lt 10 ]] || [[ $MACOS_MAJOR -eq 10 && $MACOS_MINOR -lt 15 ]]; then
        log_error "需要macOS 10.15 (Catalina)或更高版本"
        log_error "当前版本: $MACOS_VERSION"
        exit 1
    fi
    
    log "✓ macOS版本兼容"
}

# 检查并安装Homebrew
check_homebrew() {
    log "检查Homebrew..."
    
    if command -v brew &> /dev/null; then
        BREW_VERSION=$(brew --version | head -n1)
        log_info "✓ Homebrew已安装: $BREW_VERSION"
        
        # 更新Homebrew
        log_info "更新Homebrew..."
        brew update > /dev/null 2>&1 || log_warn "Homebrew更新失败"
    else
        log "安装Homebrew..."
        echo -e "${YELLOW}Homebrew未安装，正在自动安装...${NC}"
        
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
            log_error "Homebrew安装失败"
            echo -e "${RED}请手动安装Homebrew: https://brew.sh${NC}"
            exit 1
        }
        
        # 设置PATH（针对Apple Silicon Mac）
        if [[ $(uname -m) == "arm64" ]]; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
            eval "$(/opt/homebrew/bin/brew shellenv)"
        else
            echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
            eval "$(/usr/local/bin/brew shellenv)"
        fi
        
        log "✓ Homebrew安装完成"
    fi
}

# 使用Homebrew安装依赖
install_dependencies_with_brew() {
    log "使用Homebrew安装依赖..."
    
    local deps_to_install=()
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_info "将安装Docker..."
        deps_to_install+=("docker")
    else
        log_info "✓ Docker已安装: $(docker --version | cut -d' ' -f3 | cut -d',' -f1)"
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_info "将安装Docker Compose..."
        deps_to_install+=("docker-compose")
    else
        log_info "✓ Docker Compose已安装"
    fi
    
    # 检查Python 3
    if ! command -v python3 &> /dev/null; then
        log_info "将安装Python 3..."
        deps_to_install+=("python@3.11")
    else
        log_info "✓ Python 3已安装: $(python3 --version | cut -d' ' -f2)"
    fi
    
    # 检查Git
    if ! command -v git &> /dev/null; then
        log_info "将安装Git..."
        deps_to_install+=("git")
    else
        log_info "✓ Git已安装: $(git --version | cut -d' ' -f3)"
    fi
    
    # 安装缺失的依赖
    if [ ${#deps_to_install[@]} -gt 0 ]; then
        log "安装依赖: ${deps_to_install[*]}"
        
        for dep in "${deps_to_install[@]}"; do
            case $dep in
                "docker")
                    # 安装Docker Desktop for Mac
                    if ! brew list --cask docker &> /dev/null; then
                        log_info "安装Docker Desktop..."
                        brew install --cask docker || {
                            log_error "Docker安装失败"
                            echo -e "${YELLOW}请手动安装Docker Desktop: https://www.docker.com/products/docker-desktop${NC}"
                            exit 1
                        }
                        
                        # 提示启动Docker Desktop
                        echo -e "${YELLOW}请启动Docker Desktop应用程序，然后按Enter继续...${NC}"
                        read -r
                    fi
                    ;;
                *)
                    brew install "$dep" || log_warn "$dep 安装失败"
                    ;;
            esac
        done
    fi
    
    # 等待Docker启动
    if command -v docker &> /dev/null; then
        log "等待Docker服务启动..."
        local max_attempts=30
        local attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            if docker info &> /dev/null; then
                log "✓ Docker服务已就绪"
                break
            fi
            
            log_info "等待Docker启动... ($attempt/$max_attempts)"
            sleep 5
            ((attempt++))
        done
        
        if [ $attempt -gt $max_attempts ]; then
            log_warn "Docker启动超时，请确保Docker Desktop正在运行"
        fi
    fi
    
    log "✓ 所有依赖安装完成"
}

# macOS特定的Claude CLI检查
check_claude_cli_macos() {
    log "检查Claude CLI (macOS)..."
    
    # 检查多种安装方式
    if command -v claude &> /dev/null; then
        CLAUDE_VERSION=$(claude --version 2>/dev/null | head -n1 || echo "unknown")
        log_info "✓ Claude CLI已安装: $CLAUDE_VERSION"
        CLAUDE_CLI_READY=true
    elif command -v npx &> /dev/null && npx claude --version &> /dev/null; then
        log_info "✓ Claude CLI通过npx可用"
        CLAUDE_CLI_READY=true
    else
        log_warn "Claude CLI未安装"
        echo -e "${YELLOW}推荐的安装方法:${NC}"
        echo "  1. 使用npm: npm install -g @anthropic/claude-cli"
        echo "  2. 使用Homebrew: brew install claude-cli (如果可用)"
        echo "  3. 下载二进制文件: https://github.com/anthropics/claude-cli/releases"
        echo
        
        read -p "是否继续安装(Claude CLI将稍后配置)? [y/N]: " -r
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        CLAUDE_CLI_READY=false
    fi
    
    # 检查配置目录
    CLAUDE_CONFIG_DIR="$HOME/.claude"
    if [ -f "$CLAUDE_CONFIG_DIR/claude.json" ]; then
        log_info "✓ Claude CLI配置文件存在"
    else
        log_warn "Claude CLI配置文件不存在，将创建默认配置"
    fi
}

# 创建macOS优化的启动器
create_macos_launcher() {
    log "创建macOS启动器..."
    
    # 创建LaunchAgent plist文件
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_file="$plist_dir/com.claude.memory.mcp.plist"
    
    mkdir -p "$plist_dir"
    
    cat > "$plist_file" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.memory.mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd $SCRIPT_DIR && docker-compose -f docker-compose.global.yml up</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/.claude-memory/logs/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.claude-memory/logs/launchd.err.log</string>
</dict>
</plist>
EOF
    
    log_info "✓ LaunchAgent配置已创建: $plist_file"
    
    # 创建便捷的启动/停止脚本
    cat > "$HOME/.claude-memory/start_service.sh" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
docker-compose -f docker-compose.global.yml up -d
echo "Claude Memory MCP服务已启动"
EOF
    
    cat > "$HOME/.claude-memory/stop_service.sh" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
docker-compose -f docker-compose.global.yml down
echo "Claude Memory MCP服务已停止"
EOF
    
    chmod +x "$HOME/.claude-memory/start_service.sh"
    chmod +x "$HOME/.claude-memory/stop_service.sh"
    
    log_info "✓ 便捷启动脚本已创建"
}

# 显示macOS特定的结果
show_macos_results() {
    echo
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║              🍎 macOS安装成功完成! 🍎                         ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo
    
    echo -e "${CYAN}📋 服务信息:${NC}"
    echo -e "  🔗 MCP服务地址: localhost:6334"
    echo -e "  📁 全局数据目录: $HOME/.claude-memory"
    echo -e "  🐳 Docker容器: claude-memory-global"
    echo -e "  📊 Vector数据库: localhost:6335"
    echo
    
    echo -e "${CYAN}🚀 macOS快速启动:${NC}"
    echo -e "  快速启动: ${GREEN}~/.claude-memory/start_service.sh${NC}"
    echo -e "  快速停止: ${GREEN}~/.claude-memory/stop_service.sh${NC}"
    echo -e "  LaunchAgent: ${GREEN}launchctl load ~/Library/LaunchAgents/com.claude.memory.mcp.plist${NC}"
    echo
    
    echo -e "${CYAN}🍺 Homebrew管理:${NC}"
    echo -e "  升级服务: ${GREEN}brew upgrade docker docker-compose${NC}"
    echo -e "  卸载依赖: ${GREEN}brew uninstall --cask docker${NC}"
    echo
    
    echo -e "${CYAN}⌨️  macOS快捷键:${NC}"
    echo -e "  启动Docker Desktop: ${GREEN}Command + Space → 输入 'Docker'${NC}"
    echo -e "  查看系统日志: ${GREEN}Console.app → 搜索 'claude-memory'${NC}"
    echo
    
    echo -e "${CYAN}🛠️  终端命令:${NC}"
    echo -e "  启动服务: ${GREEN}docker-compose -f $SCRIPT_DIR/docker-compose.global.yml up -d${NC}"
    echo -e "  停止服务: ${GREEN}docker-compose -f $SCRIPT_DIR/docker-compose.global.yml down${NC}"
    echo -e "  查看日志: ${GREEN}docker logs claude-memory-global${NC}"
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
        echo -e "  请先安装Claude CLI:"
        echo -e "  ${GREEN}npm install -g @anthropic/claude-cli${NC}"
        echo -e "  然后运行: ${GREEN}$SCRIPT_DIR/scripts/configure_claude_cli.sh${NC}"
        echo
    fi
    
    echo -e "${CYAN}🔍 macOS故障排除:${NC}"
    echo -e "  安装日志: ${GREEN}$LOG_FILE${NC}"
    echo -e "  Docker状态: ${GREEN}docker info${NC}"
    echo -e "  活动监视器: 搜索 'docker' 或 'claude'"
    echo -e "  系统偏好设置: 安全性与隐私 → 隐私 → 完全磁盘访问权限"
    echo
    
    echo -e "${CYAN}🎯 下一步:${NC}"
    echo -e "  1. 确保Docker Desktop正在运行"
    echo -e "  2. 配置Claude CLI (如果尚未配置)"
    echo -e "  3. 在Claude CLI中测试: ${GREEN}claude mcp call claude-memory-global ping${NC}"
    echo
}

# 主函数
main() {
    show_macos_banner
    
    echo -e "${BLUE}开始安装Claude Memory MCP全局服务 (macOS优化版)...${NC}"
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
    
    # macOS特定检查
    check_macos_version
    check_homebrew
    install_dependencies_with_brew
    check_claude_cli_macos
    
    # 执行通用安装步骤
    mkdir -p "$HOME/.claude-memory"/{data,logs,config,cache,postgres,qdrant}
    log "✓ 全局数据目录创建完成"
    
    # 复制配置文件
    if [ ! -f "$HOME/.claude-memory/config/global_config.yml" ]; then
        cp "$SCRIPT_DIR/config/global_config.yml" "$HOME/.claude-memory/config/"
        log_info "✓ 默认配置文件已创建"
    fi
    
    # 构建和启动服务
    cd "$SCRIPT_DIR"
    
    if [ "$skip_build" != true ]; then
        log "构建Docker镜像..."
        docker build -f Dockerfile.global -t claude-memory-global:$VERSION . || {
            log_error "Docker镜像构建失败"
            exit 1
        }
        log "✓ Docker镜像构建完成"
    fi
    
    # 停止现有服务
    if docker-compose -f docker-compose.global.yml ps | grep -q "Up"; then
        log_info "停止现有服务..."
        docker-compose -f docker-compose.global.yml down
    fi
    
    # 启动服务
    log "启动全局服务栈..."
    docker-compose -f docker-compose.global.yml up -d || {
        log_error "服务启动失败"
        exit 1
    }
    
    # 配置Claude CLI
    if [ "$CLAUDE_CLI_READY" = true ]; then
        mkdir -p "$CLAUDE_CONFIG_DIR"
        
        if [ -f "$CLAUDE_CONFIG_DIR/claude.json" ]; then
            cp "$CLAUDE_CONFIG_DIR/claude.json" "$CLAUDE_CONFIG_DIR/claude.json.backup.$(date +%Y%m%d_%H%M%S)"
            log_info "✓ 现有配置已备份"
        fi
        
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
    fi
    
    # 创建macOS特定组件
    create_macos_launcher
    
    # 等待服务启动
    log "等待服务就绪..."
    sleep 15
    
    # 健康检查
    if docker exec claude-memory-global python /app/healthcheck.py &>/dev/null; then
        log "✓ 服务健康检查通过"
    else
        log_warn "服务可能仍在初始化中"
    fi
    
    show_macos_results
    
    log "🎉 Claude Memory MCP全局服务 (macOS版) 安装完成!"
}

# 错误处理
trap 'log_error "安装过程中发生错误，请查看日志: $LOG_FILE"' ERR

# 运行主函数
main "$@"