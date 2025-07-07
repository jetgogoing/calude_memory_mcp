#!/bin/bash
set -e

# Claude CLI MCP 自动配置脚本
# 自动检测和配置Claude CLI以集成全局MCP服务

VERSION="2.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# 检测操作系统和Claude CLI配置路径
detect_claude_config() {
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        CLAUDE_CONFIG_DIR="$APPDATA/claude"
    else
        CLAUDE_CONFIG_DIR="$HOME/.claude"
    fi
    
    log_info "Claude CLI配置目录: $CLAUDE_CONFIG_DIR"
}

# 检查Claude CLI安装
check_claude_cli() {
    log "检查Claude CLI安装状态..."
    
    if ! command -v claude &> /dev/null; then
        log_error "Claude CLI未安装"
        echo
        echo -e "${YELLOW}请先安装Claude CLI:${NC}"
        echo
        echo "方法1 - NPM安装:"
        echo "  npm install -g @anthropic/claude-cli"
        echo
        echo "方法2 - 下载二进制文件:"
        echo "  访问: https://github.com/anthropics/claude-cli/releases"
        echo
        echo "方法3 - 使用包管理器:"
        case "$OSTYPE" in
            "darwin"*)
                echo "  brew install claude-cli"
                ;;
            "linux-gnu"*)
                echo "  # 下载并安装deb/rpm包"
                ;;
        esac
        echo
        exit 1
    fi
    
    local claude_version
    claude_version=$(claude --version 2>/dev/null | head -n1 || echo "unknown")
    log_info "✓ Claude CLI已安装: $claude_version"
}

# 读取现有配置
read_existing_config() {
    log "读取现有Claude CLI配置..."
    
    if [ -f "$CLAUDE_CONFIG_DIR/claude.json" ]; then
        # 备份现有配置
        local backup_file="$CLAUDE_CONFIG_DIR/claude.json.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$CLAUDE_CONFIG_DIR/claude.json" "$backup_file"
        log_info "✓ 现有配置已备份到: $backup_file"
        
        # 读取现有配置
        EXISTING_CONFIG=$(cat "$CLAUDE_CONFIG_DIR/claude.json")
        log_info "✓ 现有配置已读取"
    else
        log_info "未找到现有配置，将创建新配置"
        EXISTING_CONFIG="{}"
    fi
}

# 生成MCP服务器配置
generate_mcp_config() {
    log "生成全局MCP服务器配置..."
    
    # 检测容器运行状态
    if docker ps | grep -q "claude-memory-global"; then
        CONNECTION_TYPE="docker_exec"
        log_info "检测到Docker容器运行中，使用docker exec连接"
    elif netstat -ln 2>/dev/null | grep -q ":6334" || ss -ln 2>/dev/null | grep -q ":6334"; then
        CONNECTION_TYPE="tcp"
        log_info "检测到TCP端口6334开放，使用TCP连接"
    else
        CONNECTION_TYPE="stdio"
        log_warn "未检测到运行中的服务，使用stdio连接"
    fi
    
    # 根据连接类型生成配置
    case $CONNECTION_TYPE in
        "docker_exec")
            MCP_SERVER_CONFIG=$(cat << 'EOF'
{
  "command": "docker",
  "args": ["exec", "-i", "claude-memory-global", "python", "/app/global_mcp_server.py"],
  "env": {}
}
EOF
)
            ;;
        "tcp")
            MCP_SERVER_CONFIG=$(cat << 'EOF'
{
  "command": "nc",
  "args": ["localhost", "6334"],
  "env": {}
}
EOF
)
            ;;
        "stdio")
            MCP_SERVER_CONFIG=$(cat << 'EOF'
{
  "command": "python",
  "args": ["/path/to/global_mcp_server.py"],
  "env": {"PYTHONPATH": "/path/to/src"}
}
EOF
)
            ;;
    esac
    
    log_info "✓ MCP服务器配置已生成 (连接类型: $CONNECTION_TYPE)"
}

# 合并配置
merge_configurations() {
    log "合并Claude CLI配置..."
    
    # 使用Python进行JSON合并
    local merged_config
    merged_config=$(python3 << EOF
import json
import sys

try:
    # 读取现有配置
    existing = json.loads('''$EXISTING_CONFIG''')
    
    # 新的MCP服务器配置
    new_mcp_config = json.loads('''$MCP_SERVER_CONFIG''')
    
    # 确保mcpServers字段存在
    if 'mcpServers' not in existing:
        existing['mcpServers'] = {}
    
    # 添加或更新claude-memory-global配置
    existing['mcpServers']['claude-memory-global'] = new_mcp_config
    
    # 输出合并后的配置
    print(json.dumps(existing, indent=2, ensure_ascii=False))
    
except Exception as e:
    print(f"配置合并失败: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)
    
    if [ $? -eq 0 ]; then
        FINAL_CONFIG="$merged_config"
        log_info "✓ 配置合并成功"
    else
        log_error "配置合并失败"
        exit 1
    fi
}

# 写入配置文件
write_config() {
    log "写入Claude CLI配置文件..."
    
    # 确保配置目录存在
    mkdir -p "$CLAUDE_CONFIG_DIR"
    
    # 写入配置
    echo "$FINAL_CONFIG" > "$CLAUDE_CONFIG_DIR/claude.json"
    
    # 验证配置文件有效性
    if python3 -m json.tool "$CLAUDE_CONFIG_DIR/claude.json" >/dev/null 2>&1; then
        log_info "✓ 配置文件格式验证通过"
    else
        log_error "配置文件格式无效"
        exit 1
    fi
    
    log "✓ Claude CLI配置文件已更新"
}

# 测试MCP连接
test_mcp_connection() {
    log "测试MCP服务器连接..."
    
    # 等待配置生效
    sleep 2
    
    # 尝试列出MCP服务器
    if claude mcp list &>/dev/null; then
        log_info "✓ MCP服务器列表获取成功"
        
        # 检查claude-memory-global是否在列表中
        if claude mcp list | grep -q "claude-memory-global"; then
            log_info "✓ claude-memory-global服务器已注册"
            
            # 尝试调用ping工具
            if claude mcp call claude-memory-global ping &>/dev/null; then
                log "✓ MCP服务器连接测试成功"
                return 0
            else
                log_warn "MCP服务器响应测试失败"
                return 1
            fi
        else
            log_warn "claude-memory-global服务器未在列表中找到"
            return 1
        fi
    else
        log_warn "无法获取MCP服务器列表"
        return 1
    fi
}

# 显示配置结果
show_configuration_result() {
    echo
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║              🔧 Claude CLI配置完成! 🔧                        ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo
    
    echo -e "${BLUE}📋 配置信息:${NC}"
    echo -e "  配置文件: ${GREEN}$CLAUDE_CONFIG_DIR/claude.json${NC}"
    echo -e "  MCP服务器: ${GREEN}claude-memory-global${NC}"
    echo -e "  连接类型: ${GREEN}$CONNECTION_TYPE${NC}"
    echo
    
    echo -e "${BLUE}🚀 使用方法:${NC}"
    echo -e "  1. 打开终端并运行Claude CLI"
    echo -e "  2. 列出MCP服务器: ${GREEN}claude mcp list${NC}"
    echo -e "  3. 调用记忆搜索: ${GREEN}claude mcp call claude-memory-global memory_search '{\"query\": \"your search\"}'${NC}"
    echo -e "  4. 获取最近对话: ${GREEN}claude mcp call claude-memory-global get_recent_conversations${NC}"
    echo
    
    echo -e "${BLUE}🛠️  可用MCP工具:${NC}"
    echo -e "  • ${GREEN}memory_search${NC} - 搜索全局对话记忆"
    echo -e "  • ${GREEN}get_recent_conversations${NC} - 获取最近对话"
    echo -e "  • ${GREEN}get_project_conversations${NC} - 获取项目对话历史"
    echo -e "  • ${GREEN}get_cross_project_memories${NC} - 跨项目记忆搜索"
    echo -e "  • ${GREEN}memory_status${NC} - 系统状态信息"
    echo -e "  • ${GREEN}memory_health${NC} - 健康检查"
    echo -e "  • ${GREEN}ping${NC} - 连接测试"
    echo
    
    echo -e "${BLUE}🔍 故障排除:${NC}"
    echo -e "  查看配置: ${GREEN}cat $CLAUDE_CONFIG_DIR/claude.json${NC}"
    echo -e "  列出服务器: ${GREEN}claude mcp list${NC}"
    echo -e "  测试连接: ${GREEN}claude mcp call claude-memory-global ping${NC}"
    echo -e "  查看服务日志: ${GREEN}docker logs claude-memory-global${NC}"
    echo
}

# 主函数
main() {
    echo -e "${BLUE}Claude CLI MCP 自动配置工具 v$VERSION${NC}"
    echo
    
    # 检测环境
    detect_claude_config
    check_claude_cli
    
    # 读取和处理配置
    read_existing_config
    generate_mcp_config
    merge_configurations
    write_config
    
    # 测试连接
    if test_mcp_connection; then
        echo -e "${GREEN}✓ 配置和连接测试成功${NC}"
    else
        echo -e "${YELLOW}⚠️  配置已完成，但连接测试失败${NC}"
        echo -e "  请确保Claude Memory全局服务正在运行"
        echo -e "  运行服务: ${GREEN}docker-compose -f ../docker-compose.global.yml up -d${NC}"
    fi
    
    show_configuration_result
    
    log "Claude CLI配置完成!"
}

# 运行主函数
main "$@"