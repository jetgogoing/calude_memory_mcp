#!/bin/bash
#
# Claude Memory 自动功能启用脚本
# 在当前shell中启用所有自动功能
#

echo "🚀 启用Claude Memory自动功能..."

# 1. 设置自动保存别名
alias claude='/home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py'
alias claude-original='/home/jetgogoing/.nvm/versions/node/v22.17.0/lib/node_modules/@anthropic-ai/claude-code/cli.js'

# 2. 加载自动注入函数
if [ -f ~/.claude_memory_functions.sh ]; then
    source ~/.claude_memory_functions.sh
    # 使用自动注入功能
    alias claude='claude_with_memory'
    echo "✅ 自动注入功能已加载"
else
    echo "⚠️  自动注入函数文件不存在"
fi

# 3. 验证配置
echo ""
echo "📊 当前配置状态："
echo "- claude命令: $(type -t claude 2>/dev/null || echo '未定义')"
echo "- claude_with_memory函数: $(type -t claude_with_memory 2>/dev/null || echo '未定义')"
echo ""

# 4. 提示信息
echo "💡 使用提示："
echo "1. 直接使用 'claude \"你的问题\"' - 会自动保存并注入记忆"
echo "2. 使用 'claude-original' 访问原始Claude"
echo "3. 查看状态: ~/.claude_memory/status.sh"
echo ""
echo "🎉 自动功能已启用！"