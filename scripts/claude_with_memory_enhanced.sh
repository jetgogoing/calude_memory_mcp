#!/bin/bash
#
# Claude Memory增强包装器
# 在每次Claude CLI调用前自动注入丰富的历史记忆
#

set -e

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="/home/jetgogoing/claude_memory/venv/bin/python"
INJECT_SCRIPT="$SCRIPT_DIR/client_inject.py"

# 获取会话ID（基于终端会话）
SESSION_ID="${CLAUDE_SESSION_ID:-$(tty | md5sum | cut -d' ' -f1)}"
export CLAUDE_SESSION_ID="$SESSION_ID"

# 检查是否是claude命令
if [[ "$1" != "claude" ]]; then
    # 不是claude命令，直接执行
    exec "$@"
fi

# 移除第一个参数 'claude'
shift

# 检查是否有用户输入
if [[ $# -eq 0 ]]; then
    # 没有参数，直接执行claude
    exec claude
fi

# 获取最后一个参数作为用户消息
ARGS=("$@")
LAST_ARG="${ARGS[-1]}"

# 检查最后一个参数是否是选项（以-开头）
if [[ "$LAST_ARG" == -* ]]; then
    # 是选项，不需要注入记忆
    exec claude "$@"
fi

# 执行记忆注入
echo "🧠 Claude Memory: 正在加载相关记忆..." >&2

# 调用Python脚本获取增强的提示
ENHANCED_PROMPT=$($PYTHON_BIN "$INJECT_SCRIPT" "$LAST_ARG" "$SESSION_ID" 2>/dev/null)

if [[ $? -eq 0 ]] && [[ -n "$ENHANCED_PROMPT" ]] && [[ "$ENHANCED_PROMPT" != "$LAST_ARG" ]]; then
    # 注入成功，替换最后一个参数
    echo "✅ Claude Memory: 已注入相关历史上下文" >&2
    
    # 重构参数，替换最后一个参数
    NEW_ARGS=("${ARGS[@]:0:${#ARGS[@]}-1}")
    exec claude "${NEW_ARGS[@]}" "$ENHANCED_PROMPT"
else
    # 注入失败或没有找到相关记忆，使用原始参数
    echo "ℹ️  Claude Memory: 使用原始输入" >&2
    exec claude "$@"
fi