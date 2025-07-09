#!/bin/bash
#
# Claude Memory 自动启动配置脚本
# 
# 功能：
# - 配置系统自动启动Claude Memory
# - 添加到 ~/.bashrc
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🔧 Claude Memory 自动启动配置${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""

# 检查是否已经配置
if grep -q "auto_start_memory_system.sh" ~/.bashrc 2>/dev/null; then
    echo -e "${YELLOW}⚠️ 自动启动已经配置过了${NC}"
    echo -e "${YELLOW}如需重新配置，请先手动编辑 ~/.bashrc 删除相关行${NC}"
    exit 0
fi

# 添加自动启动到 ~/.bashrc
echo -e "${BLUE}📝 配置 ~/.bashrc...${NC}"
cat >> ~/.bashrc << EOF

# Claude Memory 自动启动
if [ -f "$PROJECT_ROOT/auto_start_memory_system.sh" ]; then
    # 在后台静默启动，避免影响终端启动速度
    nohup "$PROJECT_ROOT/auto_start_memory_system.sh" > /dev/null 2>&1 &
fi
EOF

echo -e "${GREEN}✅ 已添加到 ~/.bashrc${NC}"

# 配置 VS Code 终端
echo -e "${BLUE}📝 配置 VS Code 设置（可选）...${NC}"
VSCODE_SETTINGS_DIR="$PROJECT_ROOT/.vscode"
VSCODE_SETTINGS_FILE="$VSCODE_SETTINGS_DIR/settings.json"

if [ ! -d "$VSCODE_SETTINGS_DIR" ]; then
    mkdir -p "$VSCODE_SETTINGS_DIR"
fi

if [ ! -f "$VSCODE_SETTINGS_FILE" ]; then
    cat > "$VSCODE_SETTINGS_FILE" << EOF
{
  "terminal.integrated.env.linux": {
    "CLAUDE_MEMORY_AUTO_START": "true"
  },
  "terminal.integrated.shellArgs.linux": [
    "-c",
    "source ~/.bashrc; exec bash"
  ]
}
EOF
    echo -e "${GREEN}✅ VS Code 设置已创建${NC}"
else
    echo -e "${YELLOW}⚠️ VS Code 设置文件已存在，请手动配置${NC}"
fi

echo ""
echo -e "${GREEN}🎉 自动启动配置完成！${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""
echo -e "${BLUE}📋 配置详情：${NC}"
echo -e "  • 新终端窗口将自动启动 Claude Memory"
echo -e "  • VS Code 终端也会自动启动"
echo -e "  • 启动过程在后台静默运行"
echo ""
echo -e "${YELLOW}💡 提示：${NC}"
echo -e "  • 配置立即生效（打开新终端测试）"
echo -e "  • 如需禁用，编辑 ~/.bashrc 删除相关行"
echo -e "  • 查看启动日志：ls -la $PROJECT_ROOT/logs/"