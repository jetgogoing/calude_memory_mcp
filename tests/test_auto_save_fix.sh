#!/bin/bash

echo "🧪 测试Claude Memory自动保存修复"
echo "================================"

# 1. 加载新的bashrc配置
echo "1️⃣ 应用新配置..."
source ~/.bashrc

# 2. 验证别名
echo ""
echo "2️⃣ 验证claude别名..."
type claude

# 3. 测试自动保存
echo ""
echo "3️⃣ 发送测试对话..."
TEST_ID="TEST-$(date +%s)"
echo "这是自动保存测试 $TEST_ID" | /home/jetgogoing/claude_memory/scripts/claude_memory_auto_save.py

# 4. 等待保存完成
echo ""
echo "4️⃣ 等待保存完成..."
sleep 5

# 5. 查询测试结果
echo ""
echo "5️⃣ 查询保存结果..."
curl -s -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$TEST_ID\", \"limit\": 5}" | python3 -m json.tool

echo ""
echo "✅ 测试完成！"