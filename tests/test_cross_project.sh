#!/bin/bash
#
# 测试跨项目记忆共享功能
#

set -e

echo "🧪 测试 Claude Memory 跨项目共享功能"
echo "====================================="
echo ""

# 创建测试目录
TEST_DIR="/tmp/claude_memory_test_$(date +%s)"
mkdir -p "$TEST_DIR"

# 克隆项目（模拟其他用户）
echo "📦 模拟克隆项目到测试目录..."
cp -r . "$TEST_DIR/claude_memory"
cd "$TEST_DIR/claude_memory"

# 清理本地特定文件
rm -rf venv .env logs/* 2>/dev/null || true

echo ""
echo "🔧 设置测试环境..."

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
echo "📥 安装依赖..."
pip install -r mcp/requirements.txt -q

# 创建测试项目
TEST_PROJECT="$TEST_DIR/my_test_project"
mkdir -p "$TEST_PROJECT"
cd "$TEST_PROJECT"

# 创建项目配置
cat > .claude.json << EOF
{
  "projectId": "test_project_$(date +%s)"
}
EOF

# 创建 .mcp.json 引用共享的 claude-memory
cat > .mcp.json << EOF
{
  "mcp": "claude-memory"
}
EOF

echo ""
echo "✅ 测试环境准备完成"
echo ""
echo "📋 测试结果："
echo "- 项目位置: $TEST_PROJECT"
echo "- 项目ID: $(cat .claude.json | grep projectId | cut -d'"' -f4)"
echo "- MCP 配置: $(cat .mcp.json)"
echo ""
echo "🚀 启动脚本测试..."

# 测试启动脚本
cd "$TEST_DIR/claude_memory"
if bash -c "timeout 5s ./mcp/start.sh" 2>&1 | grep -q "Starting Claude Memory MCP Server"; then
    echo "✅ 启动脚本工作正常"
else
    echo "❌ 启动脚本测试失败"
fi

echo ""
echo "📝 使用说明："
echo "1. 将以下配置添加到 ~/.config/claude/claude_desktop_config.json："
echo ""
echo '{
  "mcpServers": {
    "claude-memory": {
      "command": "./mcp/start.sh",
      "cwd": ".",
      "env": {
        "PYTHONPATH": "./src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}'
echo ""
echo "2. 在任意项目中创建 .mcp.json 文件："
echo '{"mcp": "claude-memory"}'
echo ""
echo "3. 启动 Claude CLI 即可自动加载记忆服务"
echo ""
echo "🧹 清理测试环境..."
cd /tmp
rm -rf "$TEST_DIR"

echo "✅ 测试完成！"