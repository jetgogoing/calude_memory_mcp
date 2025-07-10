#!/bin/bash
#
# Claude Memory Auto Save 测试脚本
#

echo "🧪 Claude Memory Auto Save 测试"
echo "================================"
echo ""

# 设置测试环境
export CLAUDE_MEMORY_DEBUG=true

# 测试1: 检查包装器脚本
echo "1️⃣ 测试包装器脚本..."
if python3 scripts/claude_memory_auto_save.py --version 2>&1 | grep -q "claude"; then
    echo "✅ 包装器可以调用Claude"
else
    echo "❌ 包装器调用失败"
    exit 1
fi

# 测试2: 测试简单对话
echo ""
echo "2️⃣ 测试简单对话捕获..."
TEST_INPUT="Hello, this is a test message for auto save"
echo "$TEST_INPUT" | python3 scripts/claude_memory_auto_save.py

# 等待异步保存
sleep 2

# 检查日志
if [ -f ~/.claude_memory/auto_save.log ]; then
    echo "✅ 日志文件已创建"
    echo "   最新日志:"
    tail -5 ~/.claude_memory/auto_save.log
else
    echo "⚠️  未找到日志文件"
fi

# 测试3: 检查会话文件
echo ""
echo "3️⃣ 检查会话文件..."
SESSION_COUNT=$(ls -1 ~/.claude_memory/session_*.log 2>/dev/null | wc -l)
if [ $SESSION_COUNT -gt 0 ]; then
    echo "✅ 找到 $SESSION_COUNT 个会话文件"
    LATEST_SESSION=$(ls -t ~/.claude_memory/session_*.log | head -1)
    echo "   最新会话: $LATEST_SESSION"
    echo "   内容预览:"
    head -10 "$LATEST_SESSION" | sed 's/^/   /'
else
    echo "⚠️  未找到会话文件"
fi

# 测试4: 检查队列
echo ""
echo "4️⃣ 检查失败队列..."
QUEUE_COUNT=$(ls -1 ~/.claude_memory/queue/*.json 2>/dev/null | wc -l)
if [ $QUEUE_COUNT -gt 0 ]; then
    echo "📦 队列中有 $QUEUE_COUNT 条待处理消息"
    echo "   这可能是因为MCP服务未运行"
else
    echo "✅ 队列为空"
fi

# 测试5: MCP连接测试
echo ""
echo "5️⃣ 测试MCP服务连接..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ MCP服务正常"
    
    # 尝试查询最新记忆
    echo "   尝试查询最新记忆..."
    SEARCH_RESULT=$(curl -s -X POST http://localhost:8000/memory/search \
        -H "Content-Type: application/json" \
        -d '{"query": "test message for auto save", "limit": 1}' 2>/dev/null)
    
    if echo "$SEARCH_RESULT" | grep -q "results"; then
        echo "✅ 记忆查询成功"
    else
        echo "⚠️  记忆查询未返回结果"
    fi
else
    echo "❌ MCP服务未运行"
    echo "   请先启动MCP服务: cd ~/claude_memory && ./scripts/start_all_services.sh"
fi

echo ""
echo "📊 测试总结"
echo "==========="
echo "• 包装器脚本: ✅"
echo "• 对话捕获: $([ $SESSION_COUNT -gt 0 ] && echo '✅' || echo '⚠️ ')"
echo "• MCP集成: $(curl -s http://localhost:8000/health > /dev/null 2>&1 && echo '✅' || echo '❌')"
echo "• 失败恢复: $([ $QUEUE_COUNT -gt 0 ] && echo '✅ 有队列文件' || echo '✅ 队列为空')"
echo ""