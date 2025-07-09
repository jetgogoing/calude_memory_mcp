# Claude Memory Docker 部署指南

## 🚀 快速开始

### 1. 准备环境变量
```bash
cp .env.docker.example .env
# 编辑 .env 文件，填入实际的 API Keys
```

### 2. 构建并启动服务
```bash
# 启动所有服务（PostgreSQL + Qdrant + Claude Memory MCP）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f claude-memory
```

### 3. 验证服务
```bash
# 检查 PostgreSQL
docker-compose exec postgres psql -U claude_memory -c "\dt"

# 检查 Qdrant
curl http://localhost:6333/health

# 查看 Claude Memory 日志
docker-compose logs claude-memory
```

## 📦 运行模式

### MCP 模式（默认）
```bash
# 作为 MCP 服务器运行，供 Claude CLI 使用
docker-compose up -d
```

### API 模式
```bash
# 作为 HTTP API 服务器运行
SERVICE_MODE=api docker-compose up -d

# 或者使用独立的 API 服务
docker-compose --profile api up -d claude-memory-api
```

### 双模式
```bash
# 同时运行 MCP 和 API
SERVICE_MODE=both docker-compose up -d
```

## 🔧 配置说明

### 环境变量
- `SERVICE_MODE`: 运行模式（mcp/api/both）
- `CLAUDE_MEMORY_PROJECT_ID`: 全局项目ID（默认: global）
- `POSTGRES_*`: PostgreSQL 连接配置
- `QDRANT_*`: Qdrant 连接配置
- `*_API_KEY`: 各种 AI 服务的 API Keys

### 端口映射
- `5433`: PostgreSQL（宿主机端口）
- `6333`: Qdrant
- `8000`: API 服务器（如果启用）

### 数据持久化
- PostgreSQL 数据: `postgres_data` volume
- Qdrant 数据: `qdrant_data` volume
- 日志文件: `./logs` 目录
- 存储文件: `./storage` 目录

## 🏗️ 构建自定义镜像

### 构建镜像
```bash
docker build -t claude-memory:latest .
```

### 推送到私有仓库
```bash
docker tag claude-memory:latest your-registry/claude-memory:latest
docker push your-registry/claude-memory:latest
```

## 🔗 与 Claude CLI 集成

### 1. 更新 Claude CLI 配置
确保 `~/.claude.json` 中的全局 mcpServers 包含：
```json
{
  "mcpServers": {
    "claude-memory": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "host",
        "-e", "CLAUDE_MEMORY_PROJECT_ID=${CLAUDE_MEMORY_PROJECT_ID:-global}",
        "claude-memory:latest",
        "mcp"
      ],
      "env": {}
    }
  }
}
```

### 2. 使用 Docker Compose 网络
```json
{
  "mcpServers": {
    "claude-memory": {
      "type": "stdio",
      "command": "docker-compose",
      "args": [
        "-f", "/home/jetgogoing/claude_memory/docker-compose.yml",
        "exec", "-T", "claude-memory",
        "python", "-m", "claude_memory.mcp_server"
      ],
      "env": {}
    }
  }
}
```

## 📊 监控和维护

### 查看资源使用
```bash
docker stats claude-memory postgres qdrant
```

### 备份数据
```bash
# 备份 PostgreSQL
docker-compose exec postgres pg_dump -U claude_memory > backup.sql

# 备份 Qdrant
docker-compose exec qdrant tar -czf /tmp/qdrant-backup.tar.gz /qdrant/storage
docker cp $(docker-compose ps -q qdrant):/tmp/qdrant-backup.tar.gz ./
```

### 清理和重置
```bash
# 停止并删除容器
docker-compose down

# 删除数据卷（谨慎！）
docker-compose down -v

# 清理未使用的镜像
docker image prune
```

## 🐛 故障排查

### 常见问题

1. **MCP 服务器连接失败**
   - 检查 Docker 服务是否运行
   - 验证端口没有被占用
   - 查看 docker-compose logs

2. **数据库连接错误**
   - 确保 PostgreSQL 健康检查通过
   - 检查环境变量配置
   - 验证网络连接

3. **API Keys 错误**
   - 确保 .env 文件存在且包含有效的 Keys
   - 检查环境变量是否正确传递到容器

### 调试命令
```bash
# 进入容器调试
docker-compose exec claude-memory /bin/bash

# 测试数据库连接
docker-compose exec claude-memory python -c "
from claude_memory.database.manager import DatabaseManager
db = DatabaseManager()
print('Database connection:', db.test_connection())
"

# 检查服务健康状态
docker-compose exec claude-memory python scripts/healthcheck.py
```

## 🚢 生产部署建议

1. **使用环境特定的配置**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

2. **启用健康检查和重启策略**
   ```yaml
   services:
     claude-memory:
       restart: unless-stopped
       healthcheck:
         test: ["CMD", "python", "scripts/healthcheck.py"]
         interval: 30s
         timeout: 10s
         retries: 3
   ```

3. **资源限制**
   ```yaml
   services:
     claude-memory:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 4G
           reservations:
             cpus: '1'
             memory: 2G
   ```

4. **日志管理**
   ```yaml
   services:
     claude-memory:
       logging:
         driver: "json-file"
         options:
           max-size: "10m"
           max-file: "3"
   ```