#!/bin/bash
#
# Claude CLI Pre-Message Hook
# 自动记忆注入：每次对话前都从数据库拉取相关历史记忆
#

set -e

# 获取用户输入的消息
USER_MESSAGE="$1"

# 如果消息为空，直接返回
if [ -z "$USER_MESSAGE" ]; then
    echo "$USER_MESSAGE"
    exit 0
fi

# 调用Claude Memory MCP服务进行记忆注入
ENHANCED_MESSAGE=$(cat <<EOF | claude mcp claude-memory claude_memory_inject --original_prompt "$USER_MESSAGE" --query_text "$USER_MESSAGE" --injection_mode "comprehensive" 2>/dev/null | jq -r '.enhanced_prompt // empty'
EOF
)

# 如果记忆注入成功，使用增强后的消息；否则使用原始消息
if [ -n "$ENHANCED_MESSAGE" ] && [ "$ENHANCED_MESSAGE" != "null" ]; then
    echo "$ENHANCED_MESSAGE"
else
    echo "$USER_MESSAGE"
fi