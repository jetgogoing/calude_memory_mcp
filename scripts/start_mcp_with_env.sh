#!/bin/bash
#
# Claude Memory MCP 启动脚本（带环境变量）
# 
# 功能：
# 1. 自动启动所有依赖服务
# 2. 确保 MCP Server 能够访问 .env 中的环境变量
#

# 获取脚本所在目录和项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 加载环境变量
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 设置Python路径
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

# 激活虚拟环境
source venv/bin/activate

# 自动启动所有依赖服务（如果尚未启动）
# 检查API服务是否已运行
if ! curl -s http://localhost:8000/health >/dev/null 2>&1; then
    # API服务未运行，启动所有服务
    echo "[Claude Memory] 正在自动启动依赖服务..." >&2
    "$SCRIPT_DIR/start_all_services.sh" >/dev/null 2>&1
    
    # 等待服务就绪
    for i in {1..30}; do
        if curl -s http://localhost:8000/health >/dev/null 2>&1; then
            echo "[Claude Memory] 所有服务已就绪" >&2
            break
        fi
        sleep 1
    done
fi

# 启动 MCP Server
exec python -m claude_memory.mcp_server "$@"