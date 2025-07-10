#!/bin/bash
#
# Claude Memory Auto Save 安装脚本
# 无缝部署自动保存功能
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SCRIPT="$SCRIPT_DIR/claude_memory_auto_save.py"
CLAUDE_BIN=$(which claude)

echo "🚀 Claude Memory Auto Save 安装程序"
echo "===================================="
echo ""

# 检查依赖
echo "1️⃣ 检查系统依赖..."

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 需要Python 3"
    exit 1
fi
echo "✅ Python 3 已安装"

# 检查claude命令
if [ -z "$CLAUDE_BIN" ]; then
    echo "❌ 错误: 找不到claude命令"
    exit 1
fi
echo "✅ 找到Claude: $CLAUDE_BIN"

# 检查包装器脚本
if [ ! -f "$WRAPPER_SCRIPT" ]; then
    echo "❌ 错误: 找不到包装器脚本: $WRAPPER_SCRIPT"
    exit 1
fi
echo "✅ 包装器脚本就绪"

# 创建工作目录
echo ""
echo "2️⃣ 创建工作目录..."
mkdir -p ~/.claude_memory/queue
echo "✅ 工作目录创建完成"

# 安装Python依赖
echo ""
echo "3️⃣ 安装Python依赖..."
pip3 install --user httpx &> /dev/null || true
echo "✅ 依赖安装完成"

# 备份原始claude（如果还没备份）
echo ""
echo "4️⃣ 配置命令别名..."

# 获取真实的claude路径
REAL_CLAUDE=$(readlink -f "$CLAUDE_BIN")
echo "   原始Claude路径: $REAL_CLAUDE"

# 创建别名配置
ALIAS_CONFIG="
# Claude Memory Auto Save
alias claude='$WRAPPER_SCRIPT'
alias claude-original='$REAL_CLAUDE'
"

# 检查shell配置文件
if [ -f ~/.bashrc ]; then
    SHELL_RC=~/.bashrc
elif [ -f ~/.zshrc ]; then
    SHELL_RC=~/.zshrc
else
    SHELL_RC=~/.bashrc
fi

# 备份shell配置
cp "$SHELL_RC" "$SHELL_RC.backup.$(date +%Y%m%d_%H%M%S)"

# 检查是否已经配置
if grep -q "Claude Memory Auto Save" "$SHELL_RC"; then
    echo "⚠️  检测到已有配置，跳过"
else
    echo "$ALIAS_CONFIG" >> "$SHELL_RC"
    echo "✅ 已添加到 $SHELL_RC"
fi

# 创建快速启用/禁用脚本
echo ""
echo "5️⃣ 创建管理命令..."

# 启用脚本
cat > ~/.claude_memory/enable_auto_save.sh << 'EOF'
#!/bin/bash
echo "🟢 启用Claude Memory自动保存..."
alias claude='$HOME/claude_memory/scripts/claude_memory_auto_save.py'
echo "✅ 已启用"
EOF

# 禁用脚本
cat > ~/.claude_memory/disable_auto_save.sh << 'EOF'
#!/bin/bash
echo "🔴 禁用Claude Memory自动保存..."
unalias claude 2>/dev/null
echo "✅ 已禁用（使用原生claude）"
EOF

chmod +x ~/.claude_memory/enable_auto_save.sh
chmod +x ~/.claude_memory/disable_auto_save.sh

echo "✅ 管理命令创建完成"

# 创建状态检查脚本
cat > ~/.claude_memory/status.sh << 'EOF'
#!/bin/bash
echo "📊 Claude Memory Auto Save 状态"
echo "==============================="
echo ""

# 检查别名
if alias claude 2>/dev/null | grep -q "claude_memory_auto_save"; then
    echo "🟢 自动保存: 已启用"
else
    echo "🔴 自动保存: 未启用"
fi

# 检查MCP服务
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "🟢 MCP服务: 运行中"
else
    echo "🔴 MCP服务: 未运行"
fi

# 检查队列
QUEUE_COUNT=$(ls -1 ~/.claude_memory/queue/*.json 2>/dev/null | wc -l)
if [ $QUEUE_COUNT -gt 0 ]; then
    echo "📦 待处理队列: $QUEUE_COUNT 条"
else
    echo "✅ 待处理队列: 空"
fi

# 检查日志
if [ -f ~/.claude_memory/auto_save.log ]; then
    LAST_LOG=$(tail -1 ~/.claude_memory/auto_save.log)
    echo "📝 最后日志: $LAST_LOG"
fi

echo ""
EOF
chmod +x ~/.claude_memory/status.sh

echo ""
echo "✅ 安装完成！"
echo ""
echo "📌 重要提示："
echo "   1. 请运行以下命令使配置生效："
echo "      source $SHELL_RC"
echo ""
echo "   2. 或者打开新的终端窗口"
echo ""
echo "📝 使用说明："
echo "   - 直接使用 'claude' 命令，将自动保存对话"
echo "   - 使用 'claude-original' 访问原生Claude"
echo "   - 运行 '~/.claude_memory/status.sh' 查看状态"
echo "   - 运行 '~/.claude_memory/disable_auto_save.sh' 临时禁用"
echo "   - 运行 '~/.claude_memory/enable_auto_save.sh' 重新启用"
echo ""
echo "🎉 开始使用吧！"