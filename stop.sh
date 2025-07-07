#!/bin/bash
# Claude Memory MCP 服务停止脚本

echo "🛑 停止Claude Memory MCP服务..."

# 停止Qdrant
echo "📊 停止Qdrant..."
docker stop qdrant 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Qdrant已停止"
else
    echo "⚠️  Qdrant未在运行或停止失败"
fi

# MCP服务会在Claude CLI退出时自动停止
echo "ℹ️  MCP服务将在Claude CLI退出时自动停止"

echo ""
echo "✨ 停止完成！"