#!/bin/bash
#
# Claude Memory Auto Save 快速启动
# 一键安装和测试自动保存功能
#

set -e

echo "🚀 Claude Memory Auto Save 快速启动"
echo "===================================="
echo ""

# 检查当前目录
if [ ! -f "scripts/claude_memory_auto_save.py" ]; then
    echo "❌ 错误：请在claude_memory项目根目录运行此脚本"
    exit 1
fi

# 1. 检查MCP服务
echo "1️⃣ 检查MCP服务状态..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ MCP服务运行正常"
else
    echo "⚠️  MCP服务未运行，正在启动..."
    ./scripts/start_all_services.sh
    sleep 5
    
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ MCP服务启动成功"
    else
        echo "❌ MCP服务启动失败，请手动检查"
        exit 1
    fi
fi

# 2. 安装自动保存功能
echo ""
echo "2️⃣ 安装自动保存功能..."
./scripts/install_auto_save.sh

# 3. 配置生效提示
echo ""
echo "3️⃣ 配置生效..."
echo ""
echo "⚠️  重要：请执行以下操作之一使配置生效："
echo ""
echo "选项A：在当前终端执行"
echo "   source ~/.bashrc"
echo ""
echo "选项B：打开新的终端窗口"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 安装完成！使用说明："
echo ""
echo "1. 正常使用 claude 命令，对话会自动保存"
echo "   示例：claude \"你好，这是自动保存测试\""
echo ""
echo "2. 查看状态："
echo "   ~/.claude_memory/status.sh"
echo ""
echo "3. 查看保存的对话："
echo "   # 通过API查询"
echo "   curl -X POST http://localhost:8000/memory/search \\"
echo "        -H \"Content-Type: application/json\" \\"
echo "        -d '{\"query\": \"自动保存测试\", \"limit\": 5}'"
echo ""
echo "4. 如需禁用自动保存："
echo "   ~/.claude_memory/disable_auto_save.sh"
echo ""
echo "📖 详细文档：docs/auto_save_guide.md"
echo ""