#!/bin/bash
# Claude Memory 数据库统一执行脚本
# 一键完成数据库整理和向量化

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查依赖
check_dependencies() {
    log_info "检查依赖环境..."
    
    # 检查Python环境
    if ! command -v python3 &> /dev/null; then
        log_error "未找到Python3"
        exit 1
    fi
    
    # 检查PostgreSQL
    if ! systemctl is-active postgresql &> /dev/null; then
        log_error "PostgreSQL服务未运行"
        exit 1
    fi
    
    # 检查Qdrant
    if ! curl -s http://localhost:6333/health &> /dev/null; then
        log_warning "Qdrant未运行，尝试启动..."
        cd "$PROJECT_DIR"
        docker-compose up -d qdrant
        sleep 5
        
        if ! curl -s http://localhost:6333/health &> /dev/null; then
            log_error "Qdrant启动失败"
            exit 1
        fi
    fi
    
    log_success "环境检查通过"
}

# 安装Python依赖
install_dependencies() {
    log_info "安装Python依赖..."
    
    cd "$PROJECT_DIR"
    
    # 激活虚拟环境
    if [ -d "venv-claude-memory" ]; then
        source venv-claude-memory/bin/activate
    fi
    
    # 安装依赖
    pip install -q aiohttp asyncpg qdrant-client
    
    log_success "依赖安装完成"
}

# 执行迁移
run_migration() {
    log_info "开始数据库统一迁移..."
    
    cd "$PROJECT_DIR"
    
    # 激活虚拟环境
    if [ -d "venv-claude-memory" ]; then
        source venv-claude-memory/bin/activate
    fi
    
    # 运行迁移脚本
    python3 scripts/database_unification_and_vectorization.py
    
    if [ $? -eq 0 ]; then
        log_success "数据库统一迁移完成！"
    else
        log_error "迁移失败，请检查日志"
        exit 1
    fi
}

# 验证结果
verify_results() {
    log_info "验证迁移结果..."
    
    # 检查PostgreSQL
    PG_CONVERSATIONS=$(PGPASSWORD=password psql -h localhost -U claude_memory -d claude_memory_db -t -c "SELECT COUNT(*) FROM conversations;" 2>/dev/null | xargs)
    PG_MESSAGES=$(PGPASSWORD=password psql -h localhost -U claude_memory -d claude_memory_db -t -c "SELECT COUNT(*) FROM messages;" 2>/dev/null | xargs)
    
    log_info "PostgreSQL: $PG_CONVERSATIONS 个对话, $PG_MESSAGES 条消息"
    
    # 检查Qdrant
    QDRANT_VECTORS=$(curl -s http://localhost:6333/collections/claude_memory_vectors_v14 | jq -r '.result.points_count' 2>/dev/null || echo "0")
    
    log_info "Qdrant: $QDRANT_VECTORS 个向量"
    
    if [ "$PG_MESSAGES" -gt "0" ] && [ "$QDRANT_VECTORS" -gt "0" ]; then
        log_success "✅ 验证通过：数据库统一成功！"
        echo ""
        echo "🎉 恭喜！Claude Memory现在拥有："
        echo "   📊 PostgreSQL: 统一的聊天记录存储"
        echo "   🧠 Qdrant: 强大的语义搜索能力"
        echo "   🧹 简化的架构: 单一数据库配置"
        echo ""
        echo "现在可以使用MCP服务进行智能记忆搜索了！"
    else
        log_error "❌ 验证失败：数据迁移可能不完整"
        exit 1
    fi
}

# 主执行流程
main() {
    echo "🚀 Claude Memory 数据库统一与向量化"
    echo "====================================="
    echo ""
    echo "这将为您："
    echo "1. 📦 备份所有现有数据"
    echo "2. 🔄 将SQLite数据迁移到PostgreSQL"
    echo "3. 🧠 生成语义搜索向量存储到Qdrant"
    echo "4. 🧹 清理冗余数据库文件"
    echo "5. ⚙️ 更新配置使用PostgreSQL"
    echo ""
    echo "预估时间：5-10分钟"
    echo "预估成本：< $0.01"
    echo ""
    
    read -p "确认开始？ (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 操作已取消"
        exit 0
    fi
    
    check_dependencies
    install_dependencies
    run_migration
    verify_results
    
    echo ""
    echo "🎯 接下来可以："
    echo "   - 使用Claude CLI测试记忆搜索功能"
    echo "   - 查看 http://localhost:6333/dashboard 管理向量数据"
    echo "   - 检查PostgreSQL数据库状态"
}

main "$@"