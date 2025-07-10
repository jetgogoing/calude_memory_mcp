#!/bin/bash
#
# Claude Memory 自动注入包装器
# 在每次Claude CLI调用前自动注入历史记忆
#

set -e

# 获取原始命令参数
ORIGINAL_ARGS="$@"

# 如果是claude命令且包含用户输入，进行记忆注入
if [[ "$*" == *"claude"* ]] && [[ $# -gt 0 ]]; then
    # 提取最后一个参数作为用户消息
    USER_MESSAGE="${@: -1}"
    
    # 如果用户消息不为空且不是命令选项
    if [[ -n "$USER_MESSAGE" ]] && [[ "$USER_MESSAGE" != -* ]]; then
        echo "🧠 正在从记忆中搜索相关信息..."
        
        # 调用memory inject获取增强的prompt
        ENHANCED_PROMPT=$(claude mcp claude-memory claude_memory_inject \
            --original_prompt "$USER_MESSAGE" \
            --query_text "$USER_MESSAGE" \
            --injection_mode "comprehensive" 2>/dev/null | \
            jq -r '.enhanced_prompt // empty' 2>/dev/null)
        
        if [[ -n "$ENHANCED_PROMPT" ]] && [[ "$ENHANCED_PROMPT" != "null" ]] && [[ "$ENHANCED_PROMPT" != "empty" ]]; then
            echo "✅ 已注入相关历史记忆"
            # 替换最后一个参数为增强后的prompt
            set -- "${@:1:$(($#-1))}" "$ENHANCED_PROMPT"
        else
            echo "ℹ️  未找到相关历史记忆，使用原始问题"
        fi
    fi
fi

# 执行原始claude命令
exec claude "$@"