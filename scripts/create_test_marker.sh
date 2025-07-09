#!/bin/bash
# 创建一个带有独特标记的测试文件，用于验证全局记忆

TEST_ID=$(date +%Y%m%d_%H%M%S)
TEST_MARKER="GLOBAL_MCP_TEST_${TEST_ID}"
SECRET_CODE="SECRET_${TEST_ID}_CODE"

echo "====================================="
echo "🧪 Claude Memory 全局测试标记"
echo "====================================="
echo "测试ID: ${TEST_ID}"
echo "测试标记: ${TEST_MARKER}"
echo "秘密代码: ${SECRET_CODE}"
echo "当前项目: $(basename $(pwd))"
echo "====================================="
echo ""
echo "请记住以下信息用于跨项目验证："
echo ""
echo "1. 测试标记: ${TEST_MARKER}"
echo "2. 秘密代码: ${SECRET_CODE}"
echo "3. 验证短语: '如果你能看到这条消息，说明全局记忆正在工作'"
echo ""
echo "保存此信息到文件..."

# 保存到用户主目录
cat > ~/.claude_memory_test_marker.txt << EOF
TEST_ID=${TEST_ID}
TEST_MARKER=${TEST_MARKER}
SECRET_CODE=${SECRET_CODE}
PROJECT=$(basename $(pwd))
TIMESTAMP=$(date -Iseconds)
EOF

echo "✅ 信息已保存到: ~/.claude_memory_test_marker.txt"
echo ""
echo "请在 Claude CLI 中创建包含上述标记的对话，"
echo "然后切换到其他项目验证是否能检索到这些信息。"