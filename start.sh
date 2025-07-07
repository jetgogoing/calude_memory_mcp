#!/bin/bash
# Claude Memory MCP 服务启动脚本

echo "🚀 启动Claude Memory MCP服务..."

# 检查Qdrant是否运行
echo "📊 检查Qdrant状态..."
if ! curl -s http://localhost:6333/collections > /dev/null 2>&1; then
    echo "⚠️  Qdrant未运行，正在启动..."
    docker run -d \
        --name qdrant \
        -p 6333:6333 \
        -v $(pwd)/data/qdrant:/qdrant/storage \
        qdrant/qdrant
    
    echo "⏳ 等待Qdrant启动..."
    sleep 5
    
    if curl -s http://localhost:6333/collections > /dev/null 2>&1; then
        echo "✅ Qdrant启动成功"
    else
        echo "❌ Qdrant启动失败"
        exit 1
    fi
else
    echo "✅ Qdrant已在运行"
fi

# 部署MCP配置 - 使用生产版本
echo "🔧 配置MCP服务..."
python scripts/deploy/deploy_production.py

echo ""
echo "✨ 启动完成！"
echo ""
echo "📋 下一步："
echo "1. 重启Claude CLI"
echo "2. 测试命令: /mcp"
echo "3. 使用服务: /mcp claude-memory memory_status"