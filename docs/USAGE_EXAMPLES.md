# Claude Memory MCP 使用示例

本文档提供Claude Memory MCP服务的详细使用示例和最佳实践。

## 🚀 基础使用示例

### 1. 查看可用工具

```bash
# 列出所有MCP服务
claude mcp list

# 查看claude-memory工具
claude mcp claude-memory --help
```

### 2. 搜索记忆

```bash
# 基础搜索
claude mcp claude-memory search_memories --query "Python性能优化"

# 指定结果数量
claude mcp claude-memory search_memories --query "数据库设计" --limit 10

# 过滤特定项目
claude mcp claude-memory search_memories --query "API设计" --project_filter "web-app"
```

### 3. 获取最近对话

```bash
# 获取最近5条对话
claude mcp claude-memory get_recent_conversations --limit 5

# 获取特定项目的最近对话
claude mcp claude-memory get_recent_conversations --project_filter "mobile-app" --limit 3
```

### 4. 健康检查

```bash
# 检查服务状态
claude mcp claude-memory health_check

# 获取性能统计
claude mcp claude-memory get_performance_stats
```

## 🔄 高级使用场景

### 场景1: 跨项目知识共享

假设你在多个项目中工作，需要共享代码设计经验：

```bash
# 在项目A中搜索关于缓存设计的讨论
cd /path/to/project-a
claude mcp claude-memory search_memories --query "缓存设计模式"

# 结果会包含来自项目B、C等其他项目的相关对话
```

### 场景2: 错误解决方案查找

当遇到错误时，快速查找之前的解决方案：

```bash
# 搜索特定错误
claude mcp claude-memory search_memories --query "TypeError: 'NoneType' object"

# 搜索解决方案
claude mcp claude-memory search_memories --query "数据库连接超时解决方案"
```

### 场景3: 代码重构参考

在重构代码时，查找相关的设计讨论：

```bash
# 搜索重构经验
claude mcp claude-memory search_memories --query "代码重构最佳实践"

# 搜索特定模式
claude mcp claude-memory search_memories --query "单例模式实现"
```

## 🛠️ 开发集成示例

### Python API使用

```python
#!/usr/bin/env python3
"""
Claude Memory MCP Python API使用示例
"""

import asyncio
import sys
from pathlib import Path

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from global_mcp.global_memory_manager import GlobalMemoryManager

async def search_example():
    """搜索记忆示例"""
    
    # 配置
    config = {
        "database": {
            "url": "sqlite:///global_memory.db"
        },
        "vector_store": {
            "url": "http://localhost:6333",
            "collection_name": "global_memories"
        },
        "memory": {
            "cross_project_sharing": True,
            "project_isolation": False,
            "retention_days": 365
        }
    }
    
    # 初始化管理器
    manager = GlobalMemoryManager(config)
    await manager.initialize()
    
    try:
        # 搜索示例
        print("🔍 搜索Python相关记忆...")
        results = await manager.search_memories("Python性能优化", limit=5)
        
        for i, result in enumerate(results, 1):
            print(f"\n结果 {i}:")
            print(f"  项目: {result.get('project_name', 'Unknown')}")
            print(f"  时间: {result.get('timestamp', 'Unknown')}")
            print(f"  内容: {result.get('content', 'No content')[:100]}...")
            print(f"  相似度: {result.get('similarity', 0):.3f}")
        
        # 获取最近对话
        print("\n📅 最近对话:")
        recent = await manager.get_recent_conversations(limit=3)
        
        for i, conv in enumerate(recent, 1):
            print(f"\n对话 {i}:")
            print(f"  标题: {conv.get('title', 'Untitled')}")
            print(f"  项目: {conv.get('project_name', 'Unknown')}")
            print(f"  消息数: {len(conv.get('messages', []))}")
        
        # 健康检查
        print("\n🏥 系统健康检查:")
        health = await manager.health_check()
        print(f"  状态: {health.get('status', 'unknown')}")
        print(f"  时间: {health.get('timestamp', 'unknown')}")
        
        for check_name, check_result in health.get('checks', {}).items():
            status_icon = "✅" if check_result.get('status') == 'ok' else "❌"
            print(f"  {check_name}: {status_icon}")
            
    finally:
        await manager.close()

async def store_conversation_example():
    """存储对话示例"""
    
    config = {
        "database": {"url": "sqlite:///global_memory.db"},
        "memory": {"cross_project_sharing": True}
    }
    
    manager = GlobalMemoryManager(config)
    await manager.initialize()
    
    try:
        # 准备对话数据
        conversation_data = {
            "title": "Python异步编程讨论",
            "messages": [
                {
                    "role": "user",
                    "content": "如何在Python中实现高效的异步编程？",
                    "timestamp": "2024-01-15T10:00:00Z"
                },
                {
                    "role": "assistant", 
                    "content": "Python异步编程主要使用asyncio库。关键是理解事件循环、协程和任务的概念...",
                    "timestamp": "2024-01-15T10:01:00Z"
                }
            ],
            "metadata": {
                "tags": ["python", "asyncio", "performance"],
                "category": "programming"
            }
        }
        
        # 项目上下文
        project_context = {
            "project_name": "async-web-server",
            "project_path": "/path/to/async-web-server",
            "project_type": "web_application"
        }
        
        # 存储对话
        print("💾 存储对话到全局记忆...")
        conversation_id = await manager.store_conversation(
            conversation_data, 
            project_context
        )
        
        print(f"✅ 对话已存储，ID: {conversation_id}")
        
    finally:
        await manager.close()

async def batch_operations_example():
    """批量操作示例"""
    
    config = {
        "database": {"url": "sqlite:///global_memory.db"},
        "concurrency": {"batch_size": 10}
    }
    
    manager = GlobalMemoryManager(config)
    await manager.initialize()
    
    try:
        # 批量存储多个对话
        conversations = []
        for i in range(5):
            conversation_data = {
                "title": f"批量测试对话 {i}",
                "messages": [
                    {"role": "user", "content": f"这是测试问题 {i}"},
                    {"role": "assistant", "content": f"这是测试回答 {i}"}
                ]
            }
            
            project_context = {
                "project_name": f"test-project-{i}",
                "project_path": f"/test/project-{i}"
            }
            
            conversations.append((conversation_data, project_context))
        
        print("📦 批量存储对话...")
        conversation_ids = await manager.store_conversation_batch(conversations)
        
        print(f"✅ 批量存储完成，存储了 {len(conversation_ids)} 个对话")
        
    finally:
        await manager.close()

def main():
    """主函数"""
    print("🎯 Claude Memory MCP Python API示例")
    print("=" * 50)
    
    # 运行示例
    asyncio.run(search_example())
    print("\n" + "=" * 50)
    asyncio.run(store_conversation_example())
    print("\n" + "=" * 50)
    asyncio.run(batch_operations_example())

if __name__ == "__main__":
    main()
```

### Shell脚本集成

```bash
#!/bin/bash
# claude_memory_helper.sh - Claude Memory MCP辅助脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 搜索函数
search_memory() {
    local query="$1"
    local limit="${2:-5}"
    
    echo -e "${GREEN}🔍 搜索记忆: ${query}${NC}"
    claude mcp claude-memory search_memories --query "$query" --limit "$limit"
}

# 获取最近对话
get_recent() {
    local limit="${1:-5}"
    
    echo -e "${GREEN}📅 获取最近 ${limit} 条对话${NC}"
    claude mcp claude-memory get_recent_conversations --limit "$limit"
}

# 健康检查
health_check() {
    echo -e "${GREEN}🏥 系统健康检查${NC}"
    claude mcp claude-memory health_check
}

# 性能统计
performance_stats() {
    echo -e "${GREEN}📊 性能统计${NC}"
    claude mcp claude-memory get_performance_stats
}

# 交互式搜索
interactive_search() {
    while true; do
        echo -e "\n${YELLOW}请输入搜索关键词 (输入 'quit' 退出):${NC}"
        read -r query
        
        if [[ "$query" == "quit" ]]; then
            break
        fi
        
        if [[ -n "$query" ]]; then
            search_memory "$query"
        fi
    done
}

# 显示使用帮助
show_help() {
    echo "Claude Memory MCP 辅助脚本"
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  search <query> [limit]   搜索记忆"
    echo "  recent [limit]           获取最近对话"
    echo "  health                   健康检查"
    echo "  stats                    性能统计"
    echo "  interactive              交互式搜索"
    echo "  help                     显示帮助"
    echo ""
    echo "示例:"
    echo "  $0 search \"Python性能优化\" 10"
    echo "  $0 recent 5"
    echo "  $0 health"
}

# 主逻辑
case "$1" in
    search)
        if [[ -z "$2" ]]; then
            echo -e "${RED}错误: 请提供搜索关键词${NC}"
            exit 1
        fi
        search_memory "$2" "$3"
        ;;
    recent)
        get_recent "$2"
        ;;
    health)
        health_check
        ;;
    stats)
        performance_stats
        ;;
    interactive)
        interactive_search
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}未知选项: $1${NC}"
        show_help
        exit 1
        ;;
esac
```

### 使用辅助脚本

```bash
# 使脚本可执行
chmod +x claude_memory_helper.sh

# 搜索记忆
./claude_memory_helper.sh search "数据库设计" 10

# 获取最近对话
./claude_memory_helper.sh recent 5

# 健康检查
./claude_memory_helper.sh health

# 交互式搜索
./claude_memory_helper.sh interactive
```

## 🎯 最佳实践

### 1. 搜索优化

- **使用具体关键词**: "Redis缓存优化" 比 "缓存" 效果更好
- **组合搜索**: 使用多个相关关键词提高准确性
- **定期清理**: 定期清理过期或无关的对话

### 2. 项目组织

- **一致的项目命名**: 使用统一的项目命名规范
- **添加有意义的标签**: 为对话添加分类标签
- **定期归档**: 对长期项目进行定期归档

### 3. 性能优化

- **批量操作**: 对多个操作使用批量接口
- **合理设置缓存**: 根据使用模式调整缓存配置
- **监控性能**: 定期检查系统性能指标

### 4. 故障处理

- **日志监控**: 定期检查系统日志
- **健康检查**: 定期执行健康检查命令
- **备份策略**: 定期备份重要的对话数据

## 🚀 进阶技巧

### 1. 自定义搜索过滤器

```python
# 高级搜索示例
async def advanced_search():
    # 按时间范围搜索
    results = await manager.search_memories(
        query="API设计",
        date_range=("2024-01-01", "2024-02-01"),
        project_filter="web-api"
    )
    
    # 按相似度阈值过滤
    filtered_results = [
        r for r in results 
        if r.get('similarity', 0) > 0.8
    ]
```

### 2. 自动化工作流

```bash
#!/bin/bash
# 自动化记忆管理工作流

# 每日健康检查
if [[ "$(date +%H)" == "09" ]]; then
    ./claude_memory_helper.sh health > daily_health_$(date +%Y%m%d).log
fi

# 每周性能报告
if [[ "$(date +%u)" == "1" ]]; then
    ./claude_memory_helper.sh stats > weekly_stats_$(date +%Y%W).log
fi
```

### 3. 集成IDE

```json
// VS Code tasks.json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "搜索Claude记忆",
            "type": "shell",
            "command": "./claude_memory_helper.sh",
            "args": ["search", "${input:searchQuery}"],
            "group": "build",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "panel": "new"
            }
        }
    ],
    "inputs": [
        {
            "id": "searchQuery",
            "description": "输入搜索关键词",
            "default": "",
            "type": "promptString"
        }
    ]
}
```

这些示例展示了Claude Memory MCP服务的强大功能和灵活性。通过合理使用这些功能，你可以显著提升开发效率和知识管理能力。