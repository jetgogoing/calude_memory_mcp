#!/bin/bash
#
# Claude Memory MCP 全自动启动脚本
# 
# 功能：
# - 验证系统依赖
# - 准备Python虚拟环境
# - 调用统一启动控制器启动所有服务
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# 打印带颜色的消息
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# 检查命令是否存在
check_command() {
    local cmd=$1
    if ! command -v "$cmd" &> /dev/null; then
        print_status "$RED" "❌ 错误: $cmd 未安装"
        return 1
    fi
    return 0
}

# 主函数
main() {
    print_status "$BLUE" "🚀 Claude Memory MCP 自动启动准备"
    print_status "$BLUE" "===================================="
    echo ""
    
    # 步骤1: 检查系统依赖
    print_status "$BLUE" "🔍 检查系统依赖..."
    local all_deps_ok=true
    
    for cmd in git docker python3 pip3; do
        if check_command "$cmd"; then
            print_status "$GREEN" "  ✅ $cmd"
        else
            all_deps_ok=false
            print_status "$RED" "  ❌ $cmd"
        fi
    done
    
    if [ "$all_deps_ok" = false ]; then
        print_status "$RED" "❌ 请先安装缺失的依赖项"
        exit 1
    fi
    
    # 步骤2: 检查/创建虚拟环境
    VENV_NAME="venv"
    VENV_DIR="$PROJECT_ROOT/$VENV_NAME"
    
    if [ ! -d "$VENV_DIR" ]; then
        print_status "$YELLOW" "📦 创建Python虚拟环境..."
        python3 -m venv "$VENV_DIR"
        print_status "$GREEN" "✅ 虚拟环境创建完成"
    fi
    
    # 激活虚拟环境并更新依赖
    source "$VENV_DIR/bin/activate"
    print_status "$BLUE" "📦 更新Python依赖..."
    pip install -q -r "$PROJECT_ROOT/requirements.txt"
    print_status "$GREEN" "✅ Python环境准备就绪"
    
    # 步骤3: 调用统一启动控制器
    echo ""
    print_status "$BLUE" "🚀 转交给统一启动控制器..."
    print_status "$BLUE" "===================================="
    echo ""
    
    # 执行统一启动脚本
    if [ -f "$PROJECT_ROOT/scripts/start_all_services.sh" ]; then
        exec "$PROJECT_ROOT/scripts/start_all_services.sh"
    else
        print_status "$RED" "❌ 错误: start_all_services.sh 未找到"
        print_status "$YELLOW" "请确保统一启动控制器已创建"
        exit 1
    fi
}

# 执行主函数
main "$@"