# 🧠 Claude Memory - 部署、配置与项目管理文档

📅 文档生成日期：20250709
📘 本文档整合 Claude Memory 的部署指南、MCP 服务配置说明与多项目管理机制，为实际部署与团队使用提供完整指导。
---


---

## 📄 文件：DEPLOYMENT_GUIDE.md

# Claude Memory MCP Service 部署指南

## 概述

本指南详细说明如何部署和配置 Claude Memory MCP Service。系统已优化为使用云服务提供商，默认使用 SiliconFlow 的 DeepSeek-V2.5 模型。

## 系统架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Claude Client  │────▶│  MCP Service     │────▶│  SiliconFlow    │
└─────────────────┘     └──────────────────┘     │  DeepSeek-V2.5  │
                               │                  └─────────────────┘
                               ├──────────────────┐
                               ▼                  ▼
                        ┌──────────────┐   ┌──────────────┐
                        │  PostgreSQL  │   │   Qdrant     │
                        │  Database    │   │ Vector Store │
                        └──────────────┘   └──────────────┘
```

## 部署选项

### 选项 1: 快速部署（推荐）

使用提供的快速启动脚本：

```bash
./scripts/quick_start.sh
```

该脚本会自动：
- 检查系统依赖
- 创建虚拟环境
- 安装 Python 包
- 启动数据库服务
- 初始化数据库
- 运行健康检查

### 选项 2: Docker Compose 部署

完整的容器化部署：

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 添加 API 密钥

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f
```

### 选项 3: 手动部署

#### 步骤 1: 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# 系统依赖
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql
```

#### 步骤 2: 配置数据库

```sql
-- 创建数据库和用户
CREATE USER claude_memory WITH PASSWORD 'your_secure_password';
CREATE DATABASE claude_memory OWNER claude_memory;
GRANT ALL PRIVILEGES ON DATABASE claude_memory TO claude_memory;
```

#### 步骤 3: 启动 Qdrant

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v ./qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

## 配置详解

### 必需配置

#### API 密钥

```env
# SiliconFlow API (必需)
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxx
```

#### 数据库连接

```env
# PostgreSQL (使用非标准端口避免冲突)
DATABASE_URL=postgresql://claude_memory:password@localhost:5433/claude_memory
```

### Mini LLM 配置

系统默认配置：

```python
# 所有任务使用 SiliconFlow DeepSeek-V2.5
TaskType.CLASSIFICATION: {
    "preferred_model": "deepseek-ai/DeepSeek-V2.5",
    "provider": ModelProvider.SILICONFLOW
}
```

特点：
- 延迟：4-6秒（比 OpenRouter 快 2.8倍）
- 成本：¥1.33/百万token
- 优化的中文提示词模板
- 地理位置优势（靠近香港）

### 检索配置

```env
# 检索参数（已优化，通常无需修改）
MEMORY_RETRIEVAL_TOP_K=20  # 初始检索数量
MEMORY_RERANK_TOP_K=5      # 重排序后返回数量
```

## 性能优化

### 1. 缓存配置

缓存系统可提供 95,794倍 的性能提升：

```env
PERFORMANCE_CACHE_TTL_SECONDS=3600  # 缓存1小时
PERFORMANCE_RESPONSE_CACHE_SIZE=500  # 缓存500个响应
```

### 2. 并发控制

```env
PERFORMANCE_MAX_CONCURRENT_REQUESTS=10  # 最大并发请求
PERFORMANCE_REQUEST_TIMEOUT_SECONDS=30  # 请求超时
```

### 3. 成本控制

每日成本估算：
- 轻度使用（1000次/天）：约 ¥1.33
- 中度使用（10000次/天）：约 ¥13.3
- 重度使用（100000次/天）：约 ¥133

## 监控和维护

### 健康检查

```bash
# 检查所有服务状态
./scripts/health-check.sh

# 手动检查
curl http://localhost:8000/health
```

### 日志管理

```bash
# 查看实时日志
tail -f logs/mcp_server.log

# 查看错误
grep ERROR logs/mcp_server.log

# 查看 API 调用统计
grep "Request processed" logs/mcp_server.log | wc -l
```

### 性能监控

```bash
# 查看延迟统计
grep "latency_ms" logs/mcp_server.log | awk '{print $NF}' | sort -n

# 查看成本
grep "cost_usd" logs/mcp_server.log | awk '{sum+=$NF} END {print sum}'
```

## 故障排除

### 常见问题

#### 1. API 调用超时

原因：网络延迟或 API 服务繁忙

解决方案：
```env
# 增加超时时间
PERFORMANCE_REQUEST_TIMEOUT_SECONDS=60
```

#### 2. 内存不足

原因：缓存过大或连接池设置不当

解决方案：
```env
# 减少缓存大小
PERFORMANCE_RESPONSE_CACHE_SIZE=200
# 减少数据库连接池
DATABASE_POOL_SIZE=5
```

#### 3. 成本过高

原因：请求量大且缓存命中率低

解决方案：
- 增加缓存 TTL
- 使用批处理减少请求次数
- 在非关键任务中使用免费的备用模型

### 调试模式

启用调试日志：
```env
MONITORING_LOG_LEVEL=DEBUG
```

## 生产环境建议

### 1. 安全配置

```env
# 使用强密码
DATABASE_URL=postgresql://claude_memory:STRONG_PASSWORD_HERE@localhost:5433/claude_memory

# 限制 CORS
APP_CORS_ORIGINS=https://your-domain.com
```

### 2. 备份策略

```bash
# 数据库备份
pg_dump -U claude_memory claude_memory > backup_$(date +%Y%m%d).sql

# Qdrant 备份
docker exec qdrant qdrant-backup create /qdrant/backups/backup_$(date +%Y%m%d)
```

### 3. 监控告警

配置告警：
```env
MONITORING_ALERT_EMAIL=ops@your-company.com
MONITORING_LATENCY_ALERT_THRESHOLD_MS=10000
MONITORING_ERROR_RATE_ALERT_THRESHOLD=0.05
```

## 升级指南

1. 备份数据
2. 拉取最新代码
3. 更新依赖：`pip install -r requirements.txt`
4. 运行迁移脚本（如有）
5. 重启服务

## 支持

遇到问题时：
1. 查看日志文件
2. 运行健康检查
3. 查看 [故障排除文档](./TROUBLESHOOTING.md)
4. 提交 Issue 到项目仓库

---

**注意**：本系统已优化为使用云服务，本地模型功能已禁用。如需启用本地模型，请参考源代码中的注释。

---

## 📄 文件：MCP_CONFIGURATION_GUIDE.md

# MCP 配置指南

## 概述

Claude Memory MCP Service 通过 MCP (Model Context Protocol) 与 Claude CLI 集成。本指南说明如何正确配置 MCP 连接。

## 配置方式

### 1. Docker 部署模式（推荐）

使用 Docker 部署时，MCP 服务通过 HTTP API 提供服务。

**Claude CLI 配置** (`.claude.json`):
```json
{
  "mcpServers": {
    "claude-memory": {
      "type": "http",
      "url": "http://localhost:8000"
    }
  }
}
```

### 2. 本地开发模式

直接运行 Python 脚本时，使用 stdio 模式。

**Claude CLI 配置** (`.claude.json`):
```json
{
  "mcpServers": {
    "claude-memory": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/claude_memory/src/claude_memory/mcp_server.py"],
      "env": {
        "SILICONFLOW_API_KEY": "${SILICONFLOW_API_KEY}",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/claude_memory",
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

## 环境变量配置

### 通过 Docker Compose（推荐）

所有环境变量都在 `deploy/docker/.env` 文件中配置：

```bash
# 复制配置模板
cp .env.minimal deploy/docker/.env

# 编辑配置文件，添加 API 密钥
vim deploy/docker/.env
```

### 通过系统环境变量

也可以通过系统环境变量配置：

```bash
# Linux/macOS
export SILICONFLOW_API_KEY="your_key_here"
export DATABASE_URL="postgresql://claude_memory:password@localhost:5432/claude_memory"
export QDRANT_URL="http://localhost:6333"

# Windows
set SILICONFLOW_API_KEY=your_key_here
set DATABASE_URL=postgresql://claude_memory:password@localhost:5432/claude_memory
set QDRANT_URL=http://localhost:6333
```

## 配置优先级

1. **环境变量**（最高优先级）
2. **Docker Compose 环境配置**
3. **.env 文件**
4. **默认值**（最低优先级）

## Claude CLI 集成

### 1. 全局配置

编辑 `~/.claude.json`：

```bash
# Linux/macOS
vim ~/.claude.json

# Windows
notepad %USERPROFILE%\.claude.json
```

### 2. 项目级配置

在项目根目录创建 `.claude.json`：

```json
{
  "mcpServers": {
    "claude-memory": {
      "type": "http",
      "url": "http://localhost:8000"
    }
  }
}
```

### 3. 验证配置

```bash
# 在 Claude CLI 中测试
/mcp claude-memory memory_status
```

## 常见问题

### 1. 连接失败

**症状**：Claude CLI 无法连接到 MCP 服务器

**解决方案**：
- 确认服务已启动：`docker ps`
- 检查端口是否正确：默认 8000
- 验证防火墙设置

### 2. API 密钥错误

**症状**：服务启动但功能异常

**解决方案**：
- 检查 `.env` 文件中的 API 密钥
- 确认至少配置了一个有效的 LLM API 密钥
- 查看日志：`docker compose logs mcp-service`

### 3. 数据库连接失败

**症状**：无法保存或检索记忆

**解决方案**：
- 确认 PostgreSQL 服务运行中
- 检查数据库连接字符串
- 验证数据库用户权限

## 最佳实践

1. **使用 Docker 部署**
   - 简化配置管理
   - 确保环境一致性
   - 便于升级和维护

2. **环境变量管理**
   - 生产环境使用环境变量注入敏感信息
   - 开发环境可以使用 `.env` 文件
   - 不要将 API 密钥提交到版本控制

3. **定期备份**
   - 使用提供的备份脚本
   - 测试恢复流程
   - 保护备份文件

## 配置模板参考

### 最小化配置 (.env.minimal)
```env
POSTGRES_PASSWORD=changeme
SILICONFLOW_API_KEY=your_key_here
```

### 开发环境 (.env.development)
```env
POSTGRES_PASSWORD=dev_password
SILICONFLOW_API_KEY=sk-xxx
GEMINI_API_KEY=AIza-xxx
APP_DEBUG=true
MONITORING_LOG_LEVEL=DEBUG
```

### 生产环境 (.env.production)
```env
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
SILICONFLOW_API_KEY=${SILICONFLOW_API_KEY}
APP_DEBUG=false
MONITORING_LOG_LEVEL=INFO
PERFORMANCE_CACHE_TTL_SECONDS=7200
```

---

**注意**：`.claude.json` 是 Claude CLI 的配置文件，用于告诉 Claude CLI 如何连接到 MCP 服务器。这个文件是必需的，但其内容很简单，主要是指定服务器地址。实际的服务配置（API 密钥、数据库连接等）都通过环境变量管理。

---

## 📄 文件：PROJECT_ID_GUIDE.md

# Claude Memory MCP Service - 项目ID使用指南

## 概述

项目ID机制允许您在同一个Claude Memory实例中管理多个独立的记忆空间。每个项目的记忆是完全隔离的，确保不同项目之间的数据不会混淆。

## 核心概念

### 什么是项目ID？

- **项目ID** 是一个唯一标识符，用于区分不同的记忆空间
- 默认项目ID是 `default`
- 每个对话、记忆单元都必须属于一个项目
- 项目之间的数据完全隔离

### 使用场景

1. **多客户端管理**: 为不同客户维护独立的知识库
2. **多项目开发**: 为不同的开发项目保存独立的技术讨论
3. **环境隔离**: 开发、测试、生产环境使用不同的记忆空间
4. **团队协作**: 不同团队拥有各自的记忆库

## 快速开始

### 1. 创建新项目

```python
from claude_memory.managers.project_manager import get_project_manager

project_manager = get_project_manager()

# 创建新项目
project = project_manager.create_project(
    project_id="my_web_app",
    name="我的Web应用",
    description="Web应用开发相关的所有记忆",
    settings={
        "primary_language": "javascript",
        "framework": "react"
    }
)
```

### 2. 在特定项目中搜索记忆

通过MCP工具使用：

```json
{
    "tool": "claude_memory_search",
    "arguments": {
        "query": "React组件优化",
        "project_id": "my_web_app",
        "limit": 10
    }
}
```

通过Python API使用：

```python
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import SearchQuery

service_manager = ServiceManager()
search_query = SearchQuery(query="React组件优化")

# 在特定项目中搜索
results = await service_manager.search_memories(
    search_query, 
    project_id="my_web_app"
)
```

### 3. 收集特定项目的对话

```python
from claude_memory.collectors.conversation_collector import ConversationCollector

# 为特定项目创建收集器
collector = ConversationCollector(project_id="my_web_app")
await collector.start_collection()
```

## 项目管理

### 列出所有项目

```python
# 列出所有活跃项目
projects = project_manager.list_projects(only_active=True)

for project in projects:
    print(f"项目: {project.name} (ID: {project.id})")
    print(f"  描述: {project.description}")
    print(f"  创建时间: {project.created_at}")
```

### 获取项目统计

```python
stats = project_manager.get_project_statistics("my_web_app")

print(f"对话数量: {stats['conversation_count']}")
print(f"记忆单元: {stats['memory_unit_count']}")
print(f"总Token数: {stats['total_tokens']}")
print(f"最后活动: {stats['last_activity']}")
```

### 更新项目信息

```python
updated_project = project_manager.update_project(
    project_id="my_web_app",
    name="我的React应用",
    description="React应用开发知识库",
    settings={
        "primary_language": "typescript",
        "framework": "react",
        "version": "18.0"
    }
)
```

### 删除项目

```python
# 软删除（标记为非活跃，数据保留）
project_manager.delete_project("old_project", soft_delete=True)

# 硬删除（永久删除所有数据）
project_manager.delete_project("test_project", soft_delete=False)
```

## 配置选项

在 `.env` 文件中配置项目相关设置：

```env
# 默认项目ID
PROJECT__DEFAULT_PROJECT_ID=default

# 是否启用跨项目搜索（Phase 3功能）
PROJECT__ENABLE_CROSS_PROJECT_SEARCH=false

# 跨项目搜索最大项目数
PROJECT__MAX_PROJECTS_PER_SEARCH=5

# 项目隔离模式
# - strict: 严格隔离（默认）
# - relaxed: 宽松隔离
# - shared: 共享模式
PROJECT__PROJECT_ISOLATION_MODE=strict
```

## 最佳实践

### 1. 项目命名规范

- 使用有意义的项目ID，如 `web_app`, `ml_research`, `customer_support`
- 避免使用特殊字符，建议使用小写字母和下划线
- 保持项目ID简短但具有描述性

### 2. 项目组织策略

```python
# 按客户组织
projects = {
    "client_acme": "ACME公司项目",
    "client_xyz": "XYZ公司项目"
}

# 按技术栈组织
projects = {
    "frontend_react": "React前端项目",
    "backend_python": "Python后端项目",
    "devops_k8s": "Kubernetes运维"
}

# 按环境组织
projects = {
    "dev_env": "开发环境",
    "test_env": "测试环境",
    "prod_env": "生产环境"
}
```

### 3. 数据迁移

如果需要将记忆从一个项目迁移到另一个项目：

```python
# TODO: 实现数据迁移功能（Phase 3）
# migrate_memories(from_project="old_project", to_project="new_project")
```

### 4. 项目备份

定期备份重要项目的数据：

```python
# 获取项目的所有记忆
# TODO: 实现项目导出功能（Phase 3）
# export_project_data("important_project", "backup_20240107.json")
```

## 安全考虑

1. **访问控制**: 目前项目ID主要用于数据隔离，未来版本将支持基于项目的访问控制
2. **数据隐私**: 确保敏感项目使用独立的项目ID
3. **审计日志**: 所有项目操作都会记录在系统日志中

## 故障排除

### 问题：找不到项目的记忆

1. 确认项目ID是否正确
2. 检查项目是否处于活跃状态
3. 验证记忆是否已过期

```python
# 诊断脚本
project = project_manager.get_project("my_project")
if not project:
    print("项目不存在")
elif not project.is_active:
    print("项目已被软删除")
else:
    stats = project_manager.get_project_statistics("my_project")
    print(f"项目包含 {stats['memory_unit_count']} 个记忆单元")
```

### 问题：项目创建失败

可能原因：
- 项目ID已存在
- 项目ID包含非法字符
- 数据库连接问题

## 未来功能（路线图）

### Phase 3: 跨项目搜索
- 在多个项目中同时搜索
- 项目间记忆关联
- 全局知识图谱

### Phase 4: 高级项目管理
- 项目模板
- 项目继承
- 项目合并与分割
- 基于角色的访问控制

### Phase 5: 企业级功能
- 项目配额管理
- 成本分摊
- 审计报告
- 合规性管理

## 示例：完整的项目生命周期

```python
import asyncio
from claude_memory.managers.project_manager import get_project_manager
from claude_memory.managers.service_manager import ServiceManager

async def project_lifecycle_demo():
    project_manager = get_project_manager()
    service_manager = ServiceManager()
    
    # 1. 创建项目
    project = project_manager.create_project(
        project_id="demo_project",
        name="演示项目",
        description="用于演示完整的项目生命周期"
    )
    print(f"✅ 项目创建成功: {project.name}")
    
    # 2. 使用项目（收集对话、搜索记忆等）
    # ... 您的业务逻辑 ...
    
    # 3. 监控项目
    stats = project_manager.get_project_statistics("demo_project")
    print(f"📊 项目统计: {stats}")
    
    # 4. 更新项目
    updated = project_manager.update_project(
        "demo_project",
        description="更新后的描述"
    )
    
    # 5. 归档项目（软删除）
    project_manager.delete_project("demo_project", soft_delete=True)
    print("🗂️ 项目已归档")
    
    # 6. 恢复项目（如需要）
    project_manager.update_project(
        "demo_project",
        is_active=True
    )
    print("♻️ 项目已恢复")
    
    # 7. 永久删除（谨慎使用）
    # project_manager.delete_project("demo_project", soft_delete=False)

asyncio.run(project_lifecycle_demo())
```

## 总结

项目ID机制为Claude Memory提供了强大的多租户支持能力。通过合理使用项目ID，您可以：

- 🔒 确保不同项目的数据完全隔离
- 📊 独立追踪每个项目的使用情况
- 🎯 提供更精准的上下文相关记忆
- 🏢 支持企业级的多项目管理需求

如有任何问题或建议，请提交Issue或参与贡献！
