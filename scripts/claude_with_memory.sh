#!/bin/bash
#
# Claude Memory 智能对话函数
# 自动注入历史记忆的Claude CLI包装器
#

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

# 创建claude别名
alias claude='claude_with_memory'

echo "🎉 Claude Memory 自动注入功能已激活！"
echo "💡 现在每次使用claude命令都会自动搜索和注入相关历史记忆"
echo "🚀 请尝试问：星云智能你有印象吗？"