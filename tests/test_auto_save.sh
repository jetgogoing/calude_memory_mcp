#!/bin/bash
# Claude Memory 自动保存功能测试脚本

echo "Claude Memory 自动保存测试"
echo "=========================="
echo ""

# 测试1：检查安装状态
echo "1. 检查安装状态..."
claude-status
echo ""

# 测试2：非交互模式捕获
echo "2. 测试非交互模式..."
TEST_ID="test_$(date +%s)"
echo "发送测试消息: $TEST_ID"
claude "测试消息 $TEST_ID: 请记住这个ID"
echo ""

# 测试3：检查队列
echo "3. 检查队列状态..."
QUEUE_COUNT=$(find ~/.claude_memory/queue -name "*.json" 2>/dev/null | wc -l)
echo "队列中有 $QUEUE_COUNT 个待处理文件"

# 测试4：处理队列
if [ "$QUEUE_COUNT" -gt 0 ]; then
    echo ""
    echo "4. 处理队列..."
    python3 ~/claude_memory/scripts/queue_processor.py
fi

# 测试5：验证保存（需要等待）
echo ""
echo "5. 等待60秒后验证保存..."
echo "（API处理较慢，需要耐心等待）"
sleep 60

echo "搜索测试消息..."
curl -s -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$TEST_ID\", \"limit\": 1}" | \
  python3 -c "import sys, json; data=json.load(sys.stdin); print('✓ 找到测试消息' if data.get('count', 0) > 0 else '✗ 未找到测试消息')"

echo ""
echo "测试完成！"