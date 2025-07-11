#!/bin/bash
# 验证 ZEN 集成文件完整性

echo "验证 Claude Memory ZEN 集成文件..."
echo "================================="

# 检查文件列表
FILES=(
    "scripts/ai_conversation_hook.py"
    "scripts/quick_zen_hook.py" 
    "scripts/zen_integration_example.py"
    "scripts/zen_capture_wrapper.py"
    "scripts/install_zen_capture.sh"
    "docs/ZEN_MCP_SERVER_INTEGRATION.md"
    "docs/ZEN_AI_CAPTURE_GUIDE.md"
)

# 计数器
FOUND=0
MISSING=0

# 检查每个文件
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
        ((FOUND++))
    else
        echo "✗ $file (缺失)"
        ((MISSING++))
    fi
done

echo ""
echo "总结："
echo "- 找到文件: $FOUND"
echo "- 缺失文件: $MISSING"

# 检查 README 更新
echo ""
echo "检查 README.md 中的 ZEN 集成说明..."
if grep -q "ZEN MCP Server 集成" README.md; then
    echo "✓ README.md 已更新"
else
    echo "✗ README.md 未找到 ZEN 集成说明"
fi

echo ""
if [ $MISSING -eq 0 ]; then
    echo "✅ 所有文件都已就绪！"
    echo ""
    echo "下一步："
    echo "1. 运行安装脚本: ./scripts/install_zen_capture.sh /path/to/zen-mcp-server"
    echo "2. 查看文档: docs/ZEN_MCP_SERVER_INTEGRATION.md"
else
    echo "⚠️  有文件缺失，请检查"
fi