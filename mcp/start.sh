#!/bin/bash
#
# Claude Memory MCP Server 启动脚本（相对路径版本）
# 
# 功能：
# - 使用相对路径启动 MCP Server
# - 自动检测项目ID
# - 检查必要的服务依赖
# - 支持跨项目共享部署
#

set -e

# 定位项目根目录（相对于 mcp/start.sh）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色定义（用于日志输出到文件）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数（写入文件，不干扰 stdio）
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$PROJECT_ROOT/logs/mcp_startup.log"
}

# 创建日志目录
mkdir -p "$PROJECT_ROOT/logs"

# 自动检测项目ID
detect_project_id() {
    # 1. 优先读取 .claude.json
    if [ -f ".claude.json" ]; then
        PROJECT_ID=$(python3 -c "import json; print(json.load(open('.claude.json'))['projectId'])" 2>/dev/null || echo "")
        if [ -n "$PROJECT_ID" ] && [ "$PROJECT_ID" != "{{ auto-detect }}" ]; then
            log "Project ID from .claude.json: $PROJECT_ID"
            echo "$PROJECT_ID"
            return
        fi
    fi
    
    # 2. 使用当前目录名
    CURRENT_DIR=$(basename "$PWD")
    if [ -n "$CURRENT_DIR" ]; then
        log "Project ID from directory name: $CURRENT_DIR"
        echo "$CURRENT_DIR"
        return
    fi
    
    # 3. 使用 git 仓库名称
    if [ -d ".git" ]; then
        GIT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
        if [ -n "$GIT_REMOTE" ]; then
            GIT_REPO=$(basename "$GIT_REMOTE" .git)
            if [ -n "$GIT_REPO" ]; then
                log "Project ID from git repo: $GIT_REPO"
                echo "$GIT_REPO"
                return
            fi
        fi
    fi
    
    # 4. 默认值
    log "Using default project ID: default"
    echo "default"
}

# 检查 Python 虚拟环境
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    log "ERROR: Virtual environment not found at $PROJECT_ROOT/venv"
    log "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 激活虚拟环境
source "$PROJECT_ROOT/venv/bin/activate"
log "Virtual environment activated"

# 设置环境变量
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# 设置项目ID
export CLAUDE_MEMORY_PROJECT_ID=$(detect_project_id)
log "Using project ID: $CLAUDE_MEMORY_PROJECT_ID"

# 加载 .env 文件（如果存在）
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    log "Loaded .env file"
fi

# 检查必要的服务（不强制要求，只是警告）
check_services() {
    # 检查 PostgreSQL
    if ! nc -z localhost ${POSTGRES_PORT:-5433} 2>/dev/null; then
        log "WARNING: PostgreSQL not running on port ${POSTGRES_PORT:-5433}"
        log "Memory persistence may not work properly"
    else
        log "PostgreSQL is running"
    fi
    
    # 检查 Qdrant
    if ! nc -z localhost ${QDRANT_PORT:-6333} 2>/dev/null; then
        log "WARNING: Qdrant not running on port ${QDRANT_PORT:-6333}"
        log "Semantic search may not work properly"
    else
        log "Qdrant is running"
    fi
}

# 执行服务检查（异步，不阻塞启动）
check_services &

# 启动 MCP Server（stdio 模式）
log "Starting Claude Memory MCP Server for project: $CLAUDE_MEMORY_PROJECT_ID"
exec python -m claude_memory.mcp_server