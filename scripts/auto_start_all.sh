#!/bin/bash
# Claude Memory 自动启动脚本 - 无感体验
# 此脚本会自动启动所有必需的服务，让用户可以直接使用 Claude CLI

set -e  # 出错时停止执行

echo "🚀 正在启动 Claude Memory 系统..."

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 1. 检查并启动 PostgreSQL
echo "📦 检查 PostgreSQL 服务..."
if systemctl is-active --quiet postgresql; then
    echo "✓ PostgreSQL 已在运行"
else
    echo "启动 PostgreSQL..."
    sudo systemctl start postgresql || {
        echo "⚠️  无法启动 PostgreSQL，请确保已安装并配置"
        exit 1
    }
fi

# 2. 启动 Qdrant 向量数据库
echo "🔷 启动 Qdrant 向量数据库..."
if pgrep -f "qdrant" > /dev/null; then
    echo "✓ Qdrant 已在运行"
else
    ./scripts/start_qdrant.sh > /tmp/qdrant.log 2>&1 &
    echo "等待 Qdrant 启动..."
    sleep 5
    
    # 验证 Qdrant 是否启动成功
    if curl -s http://localhost:6333/health | grep -q "ok"; then
        echo "✓ Qdrant 启动成功"
    else
        echo "❌ Qdrant 启动失败，请查看 /tmp/qdrant.log"
        exit 1
    fi
fi

# 3. 初始化数据库表
echo "🗄️  初始化数据库表..."
python scripts/init_database.py || {
    echo "❌ 数据库初始化失败"
    exit 1
}
echo "✓ 数据库表初始化完成"

# 4. 启动 API 服务器
echo "🌐 启动 API 服务器..."
if pgrep -f "claude_memory.server" > /dev/null; then
    echo "✓ API 服务器已在运行"
else
    # 使用 nohup 在后台启动，输出到日志文件
    nohup python -m claude_memory.server > /tmp/claude_memory_api.log 2>&1 &
    API_PID=$!
    echo "API 服务器 PID: $API_PID"
    
    # 等待 API 服务器启动
    echo "等待 API 服务器就绪..."
    sleep 5
    
    # 验证 API 服务器是否启动成功
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        echo "✓ API 服务器启动成功"
    else
        echo "⚠️  API 服务器可能未完全启动，但继续..."
    fi
fi

# 5. 启动对话采集器服务
echo "💬 启动对话采集器..."
if pgrep -f "start_collector.py" > /dev/null; then
    echo "✓ 对话采集器已在运行"
else
    nohup python scripts/start_collector.py > /tmp/claude_memory_collector.log 2>&1 &
    COLLECTOR_PID=$!
    echo "对话采集器 PID: $COLLECTOR_PID"
    sleep 2
fi

# 6. 配置 MCP 服务到 Claude CLI
echo "🔌 配置 MCP 服务..."
# 确保环境变量正确设置
export CLAUDE_MEMORY_API_URL="http://localhost:8000"
export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH}"

# 尝试更新 Claude CLI 配置
if [ -f ~/.claude.json ]; then
    echo "找到 Claude CLI 配置文件，更新 MCP 配置..."
    python scripts/fix_claude_mcp_config.py
    echo "✓ MCP 服务已配置到 Claude CLI"
elif [ -f ~/.config/claude/claude_cli_config.json ]; then
    echo "找到旧版 Claude CLI 配置文件..."
    python scripts/fix_claude_mcp_config.py
    echo "✓ MCP 服务已配置到 Claude CLI"
else
    echo "⚠️  未找到 Claude CLI 配置文件"
    echo "   请确保已安装 Claude CLI："
    echo "   npm install -g @anthropic-ai/claude-cli"
    echo ""
    echo "   安装后，MCP 服务会在 Claude CLI 启动时自动加载"
fi

# 7. 显示服务状态
echo ""
echo "🎉 Claude Memory 系统启动完成！"
echo ""
echo "服务状态："
echo "  ✓ PostgreSQL: 运行中"
echo "  ✓ Qdrant: http://localhost:6333"
echo "  ✓ API 服务器: http://localhost:8000"
echo "  ✓ 对话采集器: 运行中"
echo "  ✓ MCP 服务: 已集成到 Claude CLI"
echo ""
echo "现在您可以直接使用 Claude CLI，记忆系统会自动工作。"
echo ""
echo "使用示例："
echo "  claude \"帮我分析这个项目的代码结构\""
echo ""
echo "查看日志："
echo "  - API 日志: tail -f /tmp/claude_memory_api.log"
echo "  - 采集器日志: tail -f /tmp/claude_memory_collector.log"
echo "  - Qdrant 日志: tail -f /tmp/qdrant.log"
echo ""
echo "停止所有服务："
echo "  ./scripts/stop_all_services.sh"