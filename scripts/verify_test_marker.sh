#!/bin/bash
# 验证测试标记是否存在于其他项目中

echo "====================================="
echo "🔍 验证 Claude Memory 全局记忆"
echo "====================================="

# 读取测试标记
if [ -f ~/.claude_memory_test_marker.txt ]; then
    source ~/.claude_memory_test_marker.txt
    echo "找到测试标记文件："
    echo "- 测试ID: ${TEST_ID}"
    echo "- 测试标记: ${TEST_MARKER}"
    echo "- 秘密代码: ${SECRET_CODE}"
    echo "- 原始项目: ${PROJECT}"
    echo "- 当前项目: $(basename $(pwd))"
    echo ""
    
    if [ "${PROJECT}" == "$(basename $(pwd))" ]; then
        echo "⚠️  警告：你仍在原始项目中！"
        echo "请切换到其他项目再运行此脚本。"
        exit 1
    fi
    
    echo "✅ 确认：已切换到不同的项目"
    echo ""
    echo "现在请在 Claude CLI 中询问："
    echo ""
    echo "1. '你能找到包含 ${TEST_MARKER} 的记忆吗？'"
    echo "2. '秘密代码 ${SECRET_CODE} 是什么意思？'"
    echo "3. '搜索全局测试记忆'"
    echo ""
    echo "如果 Claude 能够找到这些信息，说明全局记忆正在工作！"
else
    echo "❌ 未找到测试标记文件"
    echo "请先在 claude_memory 项目中运行 create_test_marker.sh"
    exit 1
fi