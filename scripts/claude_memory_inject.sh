#!/bin/bash
# Claude Memory 注入包装脚本
# 处理 Python 环境并调用快速注入脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 激活虚拟环境
source "$PROJECT_ROOT/venv/bin/activate" 2>/dev/null || true

# 调用 Python 脚本
exec python "$SCRIPT_DIR/fast_inject.py" "$@"