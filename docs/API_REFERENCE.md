# Claude Memory MCP API Reference

这是Claude Memory MCP服务的完整API参考文档，包含所有可用的MCP工具和函数接口。

## 🛠️ MCP工具接口

### 1. search_memories

搜索存储的对话记忆。

#### 参数

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `query` | string | ✅ | - | 搜索关键词或短语 |
| `limit` | integer | ❌ | 5 | 返回结果数量限制 |
| `project_filter` | string | ❌ | null | 过滤特定项目的结果 |
| `date_range` | array | ❌ | null | 时间范围过滤 [start_date, end_date] |
| `similarity_threshold` | float | ❌ | 0.7 | 语义相似度阈值 (0.0-1.0) |

#### 返回值

```json
{
  "results": [
    {
      "id": "conv_123456",
      "project_name": "web-app",
      "project_path": "/path/to/web-app",
      "content": "关于性能优化的讨论内容...",
      "timestamp": "2024-01-15T10:30:00Z",
      "similarity": 0.85,
      "conversation_title": "性能优化讨论",
      "message_type": "user",
      "context": {
        "file_path": "src/main.py",
        "line_number": 42
      }
    }
  ],
  "total_count": 15,
  "search_time_ms": 23.5,
  "cache_hit": true
}
```

#### 使用示例

```bash
# 基础搜索
claude mcp claude-memory search_memories --query "Python性能优化"

# 限制结果数量
claude mcp claude-memory search_memories --query "数据库设计" --limit 10

# 项目过滤
claude mcp claude-memory search_memories --query "API设计" --project_filter "backend-api"

# 高相似度结果
claude mcp claude-memory search_memories --query "缓存策略" --similarity_threshold 0.8
```

### 2. get_recent_conversations

获取最近的对话记录。

#### 参数

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `limit` | integer | ❌ | 10 | 返回对话数量限制 |
| `project_filter` | string | ❌ | null | 过滤特定项目 |
| `days_back` | integer | ❌ | 30 | 查询最近N天的对话 |
| `include_messages` | boolean | ❌ | true | 是否包含消息内容 |

#### 返回值

```json
{
  "conversations": [
    {
      "id": "conv_789012",
      "title": "API设计讨论",
      "project_name": "backend-service",
      "project_path": "/projects/backend-service",
      "created_at": "2024-01-15T09:15:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "message_count": 8,
      "participants": ["user", "assistant"],
      "tags": ["api", "design", "backend"],
      "messages": [
        {
          "id": "msg_001",
          "role": "user",
          "content": "如何设计RESTful API？",
          "timestamp": "2024-01-15T09:15:00Z"
        }
      ]
    }
  ],
  "total_count": 25,
  "query_time_ms": 15.2
}
```

#### 使用示例

```bash
# 获取最近5条对话
claude mcp claude-memory get_recent_conversations --limit 5

# 获取特定项目的最近对话
claude mcp claude-memory get_recent_conversations --project_filter "mobile-app" --limit 3

# 获取最近7天的对话
claude mcp claude-memory get_recent_conversations --days_back 7
```

### 3. store_conversation

存储当前对话到全局记忆。

#### 参数

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `conversation_data` | object | ✅ | - | 对话数据对象 |
| `project_context` | object | ❌ | auto-detect | 项目上下文信息 |
| `tags` | array | ❌ | [] | 对话标签 |
| `metadata` | object | ❌ | {} | 附加元数据 |

#### conversation_data 结构

```json
{
  "title": "对话标题",
  "messages": [
    {
      "role": "user|assistant|system",
      "content": "消息内容",
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {
        "file_path": "src/main.py",
        "line_number": 42
      }
    }
  ],
  "summary": "对话摘要（可选）",
  "category": "讨论分类（可选）"
}
```

#### project_context 结构

```json
{
  "project_name": "项目名称",
  "project_path": "/path/to/project",
  "project_type": "web_app|mobile_app|library|script",
  "git_branch": "main",
  "git_commit": "abc123def456"
}
```

#### 返回值

```json
{
  "conversation_id": "conv_345678",
  "stored_at": "2024-01-15T10:30:00Z",
  "message_count": 6,
  "project_detected": {
    "name": "web-frontend",
    "path": "/projects/web-frontend",
    "type": "web_app"
  },
  "indexing_status": "completed",
  "vector_ids": ["vec_001", "vec_002", "vec_003"]
}
```

#### 使用示例

```bash
# 存储当前对话（自动检测项目）
claude mcp claude-memory store_conversation

# 通过API存储
python -c "
import asyncio
from global_mcp.global_memory_manager import GlobalMemoryManager

async def store():
    manager = GlobalMemoryManager({})
    conversation_data = {
        'title': '性能优化讨论',
        'messages': [
            {'role': 'user', 'content': '如何优化Python性能？'},
            {'role': 'assistant', 'content': '可以考虑以下几个方面...'}
        ]
    }
    conv_id = await manager.store_conversation(conversation_data)
    print(f'对话已存储: {conv_id}')

asyncio.run(store())
"
```

### 4. health_check

检查系统健康状态。

#### 参数

无需参数。

#### 返回值

```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime_seconds": 86400,
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "ok|error",
      "response_time_ms": 12.5,
      "connection_count": 3,
      "error_message": null
    },
    "vector_store": {
      "status": "ok|error|disabled",
      "response_time_ms": 45.2,
      "collection_size": 1542,
      "error_message": null
    },
    "cache": {
      "status": "ok|error",
      "hit_rate": 0.85,
      "size": "250/1000",
      "evictions": 12
    },
    "memory_usage": {
      "status": "ok|warning|critical",
      "used_mb": 512,
      "available_mb": 1536,
      "usage_percent": 25.0
    },
    "disk_usage": {
      "status": "ok|warning|critical",
      "used_gb": 2.5,
      "available_gb": 47.5,
      "usage_percent": 5.0
    }
  }
}
```

#### 使用示例

```bash
# 健康检查
claude mcp claude-memory health_check

# 通过HTTP API
curl -X POST http://localhost:6334/health
```

### 5. get_performance_stats

获取系统性能统计信息。

#### 参数

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `include_history` | boolean | ❌ | false | 是否包含历史数据 |
| `time_range` | string | ❌ | "1h" | 统计时间范围 (1h, 6h, 24h, 7d) |

#### 返回值

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "time_range": "1h",
  "concurrent_stats": {
    "total_requests": 1250,
    "concurrent_requests": 15,
    "max_concurrent": 32,
    "avg_response_time": 0.085,
    "error_count": 3,
    "success_rate": 0.9976
  },
  "cache_stats": {
    "hits": 850,
    "misses": 150,
    "evictions": 25,
    "hit_rate": 0.85,
    "cache_size": 450,
    "max_size": 1000
  },
  "connection_pool": {
    "total_connections": 8,
    "active_connections": 3,
    "idle_connections": 5,
    "max_connections": 20,
    "queue_size": 0,
    "wait_time_ms": 2.3
  },
  "batch_queue_size": 0,
  "memory_usage": {
    "rss_mb": 256,
    "heap_mb": 189,
    "external_mb": 45
  },
  "request_distribution": {
    "search_memories": 750,
    "get_recent_conversations": 250,
    "store_conversation": 180,
    "health_check": 70
  }
}
```

#### 使用示例

```bash
# 获取性能统计
claude mcp claude-memory get_performance_stats

# 包含历史数据
claude mcp claude-memory get_performance_stats --include_history true --time_range "24h"
```

### 6. clear_cache

清除系统缓存。

#### 参数

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `cache_type` | string | ❌ | "all" | 缓存类型 (all, search, conversations, vectors) |
| `confirm` | boolean | ✅ | false | 确认清除缓存 |

#### 返回值

```json
{
  "cleared_caches": ["search", "conversations", "vectors"],
  "items_cleared": 450,
  "cache_size_before": "125MB",
  "cache_size_after": "0MB",
  "cleared_at": "2024-01-15T10:30:00Z"
}
```

#### 使用示例

```bash
# 清除所有缓存
claude mcp claude-memory clear_cache --confirm true

# 清除特定类型缓存
claude mcp claude-memory clear_cache --cache_type "search" --confirm true
```

## 🐍 Python API 接口

### GlobalMemoryManager 类

主要的记忆管理类，提供所有核心功能。

#### 初始化

```python
from global_mcp.global_memory_manager import GlobalMemoryManager

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

manager = GlobalMemoryManager(config)
await manager.initialize()
```

#### 核心方法

##### search_memories()

```python
async def search_memories(
    self,
    query: str,
    limit: int = 5,
    project_filter: Optional[str] = None,
    date_range: Optional[Tuple[str, str]] = None,
    similarity_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    搜索记忆
    
    Args:
        query: 搜索查询
        limit: 结果数量限制
        project_filter: 项目过滤器
        date_range: 日期范围
        similarity_threshold: 相似度阈值
        
    Returns:
        搜索结果列表
    """
```

##### store_conversation()

```python
async def store_conversation(
    self,
    conversation_data: Dict[str, Any],
    project_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    存储对话
    
    Args:
        conversation_data: 对话数据
        project_context: 项目上下文
        
    Returns:
        对话ID
    """
```

##### get_recent_conversations()

```python
async def get_recent_conversations(
    self,
    limit: int = 10,
    project_filter: Optional[str] = None,
    days_back: int = 30,
    include_messages: bool = True
) -> List[Dict[str, Any]]:
    """
    获取最近对话
    
    Args:
        limit: 数量限制
        project_filter: 项目过滤器
        days_back: 天数范围
        include_messages: 是否包含消息
        
    Returns:
        对话列表
    """
```

##### health_check()

```python
async def health_check(self) -> Dict[str, Any]:
    """
    健康检查
    
    Returns:
        健康状态信息
    """
```

##### get_performance_stats()

```python
async def get_performance_stats(self) -> Dict[str, Any]:
    """
    获取性能统计
    
    Returns:
        性能统计信息
    """
```

### 并发优化管理器

```python
from global_mcp.concurrent_memory_manager import ConcurrentMemoryManager, create_concurrent_manager

# 创建并发优化管理器
config = {
    "concurrency": {
        "max_connections": 20,
        "cache_size": 2000,
        "cache_ttl": 300.0,
        "max_workers": 8
    }
}

manager = create_concurrent_manager(config)
await manager.initialize()

# 并发搜索
results = await manager.search_memories_concurrent("Python性能优化", use_cache=True)

# 批量存储
conversations = [
    (conversation_data_1, project_context_1),
    (conversation_data_2, project_context_2)
]
conversation_ids = await manager.store_conversation_batch(conversations)
```

## 🔧 配置参数

### 数据库配置

```yaml
database:
  url: "sqlite:///global_memory.db"  # 数据库URL
  pool_size: 20                      # 连接池大小
  max_overflow: 30                   # 最大溢出连接数
  pool_timeout: 30                   # 连接超时时间
  pool_recycle: 3600                # 连接回收时间
```

### 向量存储配置

```yaml
vector_store:
  url: "http://localhost:6333"       # Qdrant URL
  collection_name: "global_memories" # 集合名称
  vector_size: 384                   # 向量维度
  batch_size: 100                    # 批处理大小
  timeout: 30                        # 请求超时
```

### 并发配置

```yaml
concurrency:
  max_connections: 25                # 最大连接数
  connection_timeout: 10.0           # 连接超时
  cache_size: 5000                   # 缓存大小
  cache_ttl: 600.0                   # 缓存TTL
  max_workers: 12                    # 最大工作线程
  batch_size: 50                     # 批处理大小
  batch_timeout: 5.0                 # 批处理超时
```

### 记忆管理配置

```yaml
memory:
  cross_project_sharing: true        # 跨项目共享
  project_isolation: false           # 项目隔离
  retention_days: 365                # 保留天数
  max_conversation_age_days: 90      # 最大对话年龄
  auto_cleanup_enabled: true         # 自动清理
  cleanup_interval_hours: 24         # 清理间隔
```

## 🚨 错误代码

### HTTP状态码

| 状态码 | 描述 | 解决方案 |
|--------|------|----------|
| 200 | 请求成功 | - |
| 400 | 请求参数错误 | 检查请求参数格式和必需字段 |
| 404 | 资源未找到 | 确认请求的资源存在 |
| 500 | 服务器内部错误 | 检查服务器日志，可能需要重启服务 |
| 503 | 服务不可用 | 检查依赖服务（数据库、向量存储）状态 |

### 应用错误代码

| 错误码 | 描述 | 解决方案 |
|--------|------|----------|
| `MCP_001` | 数据库连接失败 | 检查数据库配置和网络连接 |
| `MCP_002` | 向量存储连接失败 | 检查Qdrant服务状态 |
| `MCP_003` | 配置文件错误 | 验证配置文件格式和内容 |
| `MCP_004` | 权限不足 | 检查文件系统权限 |
| `MCP_005` | 缓存操作失败 | 清除缓存或重启服务 |
| `MCP_006` | 搜索查询语法错误 | 检查搜索查询格式 |
| `MCP_007` | 存储空间不足 | 清理磁盘空间 |

## 📚 使用最佳实践

### 1. 搜索优化

```python
# 好的实践：使用具体的搜索词
results = await manager.search_memories("Python asyncio性能优化", limit=10)

# 避免：使用过于泛泛的词汇
results = await manager.search_memories("优化", limit=10)
```

### 2. 批量操作

```python
# 好的实践：批量存储对话
conversations = [(data1, context1), (data2, context2), (data3, context3)]
ids = await manager.store_conversation_batch(conversations)

# 避免：逐个存储
for data, context in conversations:
    await manager.store_conversation(data, context)  # 效率低
```

### 3. 错误处理

```python
try:
    results = await manager.search_memories("查询内容")
except ConnectionError:
    # 处理连接错误
    logger.error("无法连接到数据库")
except TimeoutError:
    # 处理超时错误
    logger.error("查询超时")
except Exception as e:
    # 处理其他错误
    logger.error(f"搜索失败: {e}")
```

### 4. 资源管理

```python
# 好的实践：正确关闭连接
manager = GlobalMemoryManager(config)
try:
    await manager.initialize()
    # 执行操作
    results = await manager.search_memories("查询")
finally:
    await manager.close()  # 确保资源释放
```

这份API参考文档涵盖了Claude Memory MCP服务的所有接口和配置选项。通过合理使用这些API，您可以构建强大的记忆管理应用。