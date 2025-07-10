#!/bin/bash
#
# 测试自动记忆注入功能
#

echo "=== 测试Claude Memory自动注入功能 ==="
echo ""

# 加载claude_with_memory函数
source ~/.bashrc

echo "📝 测试问题：星云智能你有印象吗？"
echo ""

# 模拟调用
claude_with_memory "星云智能你有印象吗？"