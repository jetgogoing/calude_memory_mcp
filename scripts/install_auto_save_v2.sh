#!/bin/bash
#
# Claude Memory Auto Save V2 安装脚本
# 使用PATH拦截方式，更可靠
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Claude Memory Auto Save V2 安装程序"
echo "====================================="
echo ""

# 1. 创建用户bin目录
echo "1. 创建用户bin目录..."
mkdir -p ~/.local/bin
echo "✓ 目录创建完成"

# 2. 复制包装器脚本
echo ""
echo "2. 安装包装器脚本..."
cp "$PROJECT_ROOT/scripts/claude_memory_wrapper_v2.py" ~/.local/bin/claude
chmod +x ~/.local/bin/claude
echo "✓ 包装器安装完成"

# 3. 检查PATH配置
echo ""
echo "3. 检查PATH配置..."
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "需要添加 ~/.local/bin 到 PATH"
    
    # 检测shell类型
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC=~/.zshrc
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC=~/.bashrc
    else
        SHELL_RC=~/.bashrc
    fi
    
    # 添加PATH配置
    echo "" >> "$SHELL_RC"
    echo "# Claude Memory Auto Save V2" >> "$SHELL_RC"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    echo "✓ 已添加到 $SHELL_RC"
else
    echo "✓ PATH已正确配置"
fi

# 4. 安装Python依赖
echo ""
echo "4. 安装依赖..."
pip3 install --user requests >/dev/null 2>&1 || true
echo "✓ 依赖安装完成"

# 5. 创建管理脚本
echo ""
echo "5. 创建管理脚本..."

# 状态检查脚本
cat > ~/.local/bin/claude-status << 'EOF'
#!/bin/bash
echo "Claude Memory 状态"
echo "=================="
echo ""

# 检查包装器
if [ -x ~/.local/bin/claude ]; then
    echo "✓ 包装器已安装"
    which_claude=$(which claude)
    if [[ "$which_claude" == "$HOME/.local/bin/claude" ]]; then
        echo "✓ claude命令正确配置"
    else
        echo "! claude命令配置异常: $which_claude"
    fi
else
    echo "✗ 包装器未安装"
fi

# 检查API服务
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✓ API服务运行中"
else
    echo "✗ API服务未运行"
fi

# 检查队列
queue_count=$(find ~/.claude_memory/queue -name "*.json" 2>/dev/null | wc -l)
if [ "$queue_count" -gt 0 ]; then
    echo "! 待处理队列: $queue_count 条"
else
    echo "✓ 队列为空"
fi
EOF
chmod +x ~/.local/bin/claude-status

# 禁用脚本
cat > ~/.local/bin/claude-disable << 'EOF'
#!/bin/bash
echo "禁用Claude Memory自动保存..."
export CLAUDE_MEMORY_DISABLE=1
echo "已禁用 (仅本会话生效)"
echo "永久禁用请添加到 ~/.bashrc: export CLAUDE_MEMORY_DISABLE=1"
EOF
chmod +x ~/.local/bin/claude-disable

echo "✓ 管理脚本创建完成"

# 6. 验证安装
echo ""
echo "6. 验证安装..."
~/.local/bin/claude-status

echo ""
echo "安装完成！"
echo ""
echo "使用说明："
echo "1. 重新加载shell配置："
echo "   source ~/.bashrc  # 或 source ~/.zshrc"
echo ""
echo "2. 正常使用claude命令，对话会自动保存"
echo ""
echo "3. 管理命令："
echo "   claude-status  # 查看状态"
echo "   claude-disable # 禁用自动保存"