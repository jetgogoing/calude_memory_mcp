#!/bin/bash
#
# Claude Memory 自动功能修复脚本
# 修复自动保存和自动注入的所有问题
#

set -e

echo "🔧 Claude Memory 自动功能修复程序"
echo "===================================="
echo ""

# 1. 修复PTY包装器的API端点
echo "1️⃣ 修复PTY包装器API端点..."
sed -i 's|/memory/conversation|/conversation/store|g' /home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py

# 修复数据格式
sed -i 's|"role": "human"|"role": "user"|g' /home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py

echo "✅ API端点已修复"

# 2. 强制设置别名
echo ""
echo "2️⃣ 设置命令别名..."

# 添加到当前shell
alias claude='/home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py'
alias claude-original='/home/jetgogoing/.nvm/versions/node/v22.17.0/lib/node_modules/@anthropic-ai/claude-code/cli.js'

# 确保写入bashrc（如果还没有）
if ! grep -q "Claude Memory Auto Save" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# Claude Memory Auto Save" >> ~/.bashrc
    echo "alias claude='/home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py'" >> ~/.bashrc
    echo "alias claude-original='/home/jetgogoing/.nvm/versions/node/v22.17.0/lib/node_modules/@anthropic-ai/claude-code/cli.js'" >> ~/.bashrc
fi

echo "✅ 别名已设置"

# 3. 加载自动注入函数
echo ""
echo "3️⃣ 加载自动注入功能..."

# 定义claude_with_memory函数
claude_with_memory() {
    local user_input="$*"
    
    # 如果没有输入，直接调用原始claude
    if [[ -z "$user_input" ]]; then
        command claude
        return
    fi
    
    # 如果是命令选项（以-开头），直接调用原始claude
    if [[ "$user_input" =~ ^- ]]; then
        command claude "$@"
        return
    fi
    
    echo "🧠 正在从记忆库中搜索相关信息..."
    
    # 调用memory inject获取增强的prompt
    local enhanced_prompt
    enhanced_prompt=$(command claude mcp claude-memory claude_memory_inject \
        --original_prompt "$user_input" \
        --query_text "$user_input" \
        --injection_mode "comprehensive" 2>/dev/null | \
        jq -r '.enhanced_prompt // empty' 2>/dev/null)
    
    if [[ -n "$enhanced_prompt" ]] && [[ "$enhanced_prompt" != "null" ]] && [[ "$enhanced_prompt" != "empty" ]] && [[ "$enhanced_prompt" != "$user_input" ]]; then
        echo "✅ 已自动注入相关历史记忆"
        echo "📝 增强后的提问包含了相关背景信息"
        echo ""
        # 使用增强后的prompt调用claude
        command claude "$enhanced_prompt"
    else
        echo "ℹ️  未找到相关历史记忆，使用原始提问"
        echo ""
        # 使用原始输入调用claude
        command claude "$user_input"
    fi
}

# 导出函数
export -f claude_with_memory

# 覆盖claude别名使用自动注入
alias claude='claude_with_memory'

echo "✅ 自动注入功能已加载"

# 4. 测试配置
echo ""
echo "4️⃣ 验证配置..."

# 检查别名
if alias claude 2>/dev/null | grep -q "claude_with_memory"; then
    echo "✅ 自动注入: 已启用"
else
    echo "⚠️  自动注入: 配置异常"
fi

# 检查自动保存
if [[ -x /home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py ]]; then
    echo "✅ 自动保存: 脚本就绪"
else
    echo "❌ 自动保存: 脚本不可执行"
fi

# 检查MCP服务
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ MCP服务: 运行中"
else
    echo "❌ MCP服务: 未运行"
fi

echo ""
echo "🎉 修复完成！"
echo ""
echo "⚠️  重要提示："
echo "   1. 在当前终端执行: source /home/jetgogoing/claude_memory/fix_auto_memory.sh"
echo "   2. 或者打开新的终端窗口"
echo ""
echo "📝 测试方法："
echo "   claude \"记住这个测试：修复成功了！\""
echo "   # 等待几秒后"
echo "   claude \"你记得刚才的测试吗？\""
echo ""
echo "💡 如果自动注入太慢，可以只使用自动保存："
echo "   alias claude='/home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py'"
echo ""

# 将函数定义写入独立文件供source使用
cat > ~/.claude_memory_functions.sh << 'EOF'
# Claude Memory 自动注入函数
claude_with_memory() {
    local user_input="$*"
    
    if [[ -z "$user_input" ]]; then
        /home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py
        return
    fi
    
    if [[ "$user_input" =~ ^- ]]; then
        /home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py "$@"
        return
    fi
    
    echo "🧠 正在从记忆库中搜索相关信息..."
    
    local enhanced_prompt
    enhanced_prompt=$(/home/jetgogoing/.nvm/versions/node/v22.17.0/lib/node_modules/@anthropic-ai/claude-code/cli.js mcp claude-memory claude_memory_inject \
        --original_prompt "$user_input" \
        --query_text "$user_input" \
        --injection_mode "comprehensive" 2>/dev/null | \
        jq -r '.enhanced_prompt // empty' 2>/dev/null)
    
    if [[ -n "$enhanced_prompt" ]] && [[ "$enhanced_prompt" != "null" ]] && [[ "$enhanced_prompt" != "empty" ]] && [[ "$enhanced_prompt" != "$user_input" ]]; then
        echo "✅ 已自动注入相关历史记忆"
        echo ""
        /home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py "$enhanced_prompt"
    else
        echo "ℹ️  未找到相关历史记忆"
        echo ""
        /home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py "$user_input"
    fi
}

export -f claude_with_memory
alias claude='claude_with_memory'
EOF

echo ""
echo "💾 函数定义已保存到 ~/.claude_memory_functions.sh"
echo "   可以在任何时候执行: source ~/.claude_memory_functions.sh"