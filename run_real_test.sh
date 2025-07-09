#!/bin/bash
# 运行真实记忆注入测试

# 设置项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 设置Python路径
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src"

# 加载环境变量
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "加载 .env 文件..."
    export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
else
    echo "错误：.env 文件不存在！"
    exit 1
fi

# 运行测试
echo "开始运行真实记忆注入测试..."
python3 "$PROJECT_ROOT/scripts/test_real_memory_injection.py"