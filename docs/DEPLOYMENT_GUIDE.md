# Claude Memory MCP 部署指南

本指南详细介绍了Claude Memory MCP服务的各种部署方式和配置选项。

## 🚀 部署方式概览

### 1. 开发环境部署 (推荐新手)
- 简单快速的本地开发环境
- 适合学习和测试
- 使用SQLite数据库

### 2. 生产环境部署 (推荐)
- Docker容器化部署
- 自动化安装脚本
- 完整的监控和日志

### 3. 企业级部署
- 分布式架构
- 高可用配置
- 负载均衡

## 📋 环境要求

### 基础要求
- **操作系统**: Linux/macOS/Windows
- **Python**: 3.8+ (推荐 3.10+)
- **内存**: 最低 2GB，推荐 4GB+
- **磁盘**: 最低 1GB 可用空间
- **网络**: 如使用向量搜索需要访问 Qdrant 服务

### 可选组件
- **Docker**: 容器化部署 (推荐)
- **Qdrant**: 向量数据库 (语义搜索功能)
- **PostgreSQL**: 生产级数据库 (可选，默认SQLite)

## 🔧 方式1: 开发环境快速部署

### 1.1 克隆项目

```bash
# 克隆项目
git clone https://github.com/yourusername/claude-memory-mcp.git
cd claude-memory-mcp

# 查看项目结构
tree -L 2
```

### 1.2 设置Python环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 升级pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.global.txt
```

### 1.3 配置环境变量

```bash
# 创建环境配置文件
cat > .env << EOF
# Claude Memory MCP 环境配置
CLAUDE_MEMORY_DATA=~/.claude-memory
CLAUDE_MEMORY_DEBUG=false
QDRANT_URL=http://localhost:6333
DATABASE_URL=sqlite:///global_memory.db
EOF

# 加载环境变量
source .env
```

### 1.4 初始化数据库

```bash
# 运行初始化脚本
python -c "
import asyncio
import sys
sys.path.insert(0, 'src')
from global_mcp.global_memory_manager import GlobalMemoryManager

async def init():
    config = {
        'database': {'url': 'sqlite:///global_memory.db'},
        'memory': {'cross_project_sharing': True}
    }
    manager = GlobalMemoryManager(config)
    await manager.initialize()
    print('✅ 数据库初始化完成')
    await manager.close()

asyncio.run(init())
"
```

### 1.5 启动服务

```bash
# 启动MCP服务器
python src/global_mcp/global_mcp_server.py
```

### 1.6 配置Claude CLI

```bash
# 运行配置脚本
chmod +x configure_claude_cli.sh
./configure_claude_cli.sh

# 验证配置
claude mcp list
```

## 🐳 方式2: Docker容器化部署

### 2.1 准备Docker环境

```bash
# 检查Docker版本
docker --version
docker-compose --version

# 如未安装Docker，请参考官方文档安装
```

### 2.2 使用Docker Compose

```bash
# 启动所有服务
docker-compose -f docker-compose.global.yml up -d

# 查看服务状态
docker-compose -f docker-compose.global.yml ps

# 查看日志
docker-compose -f docker-compose.global.yml logs claude-memory-global
```

### 2.3 服务验证

```bash
# 健康检查
curl -X POST http://localhost:6334/health

# 配置Claude CLI指向容器服务
cat > ~/.claude.json << EOF
{
  "mcpServers": {
    "claude-memory-global": {
      "command": "docker",
      "args": ["exec", "claude-memory-global", "python", "/app/global_mcp_server.py"],
      "cwd": "/app"
    }
  }
}
EOF
```

## 🚀 方式3: 一键安装脚本部署

### 3.1 运行安装脚本

```bash
# 下载并运行安装脚本
curl -fsSL https://raw.githubusercontent.com/yourusername/claude-memory-mcp/main/install_claude_memory.sh | bash

# 或者本地运行
chmod +x install_claude_memory.sh
./install_claude_memory.sh
```

### 3.2 安装脚本功能

安装脚本将自动执行：

1. **环境检查**: 验证Python、Docker等依赖
2. **项目下载**: 克隆最新版本代码
3. **依赖安装**: 自动安装Python依赖包
4. **服务配置**: 创建配置文件和环境变量
5. **Claude CLI配置**: 自动配置MCP服务器
6. **服务启动**: 启动MCP服务器
7. **验证测试**: 运行基础功能测试

### 3.3 自定义安装选项

```bash
# 指定安装目录
INSTALL_DIR=/opt/claude-memory ./install_claude_memory.sh

# 启用调试模式
DEBUG=true ./install_claude_memory.sh

# 跳过Docker安装
SKIP_DOCKER=true ./install_claude_memory.sh

# 使用PostgreSQL
USE_POSTGRES=true ./install_claude_memory.sh
```

## 🏢 方式4: 企业级生产部署

### 4.1 架构规划

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Load Balancer │  │   Claude CLI    │  │   Monitoring    │
│    (Nginx)      │  │   Instances     │  │   (Grafana)     │
└─────────┬───────┘  └─────────┬───────┘  └─────────┬───────┘
          │                    │                    │
    ┌─────┴─────────────────────┴────────────────────┴─────┐
    │                 Network Layer                        │
    └─────┬─────────────────────┬─────────────────────┬─────┘
          │                     │                     │
┌─────────┴───────┐  ┌─────────┴───────┐  ┌─────────┴───────┐
│ MCP Server 1    │  │ MCP Server 2    │  │ MCP Server 3    │
│ (Container)     │  │ (Container)     │  │ (Container)     │
└─────────┬───────┘  └─────────┬───────┘  └─────────┬───────┘
          │                     │                     │
    ┌─────┴─────────────────────┴─────────────────────┴─────┐
    │                Database Layer                         │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
    │  │ PostgreSQL  │  │   Qdrant    │  │    Redis    │   │
    │  │  (Primary)  │  │  (Vector)   │  │   (Cache)   │   │
    │  └─────────────┘  └─────────────┘  └─────────────┘   │
    └───────────────────────────────────────────────────────┘
```

### 4.2 数据库集群配置

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  # PostgreSQL主数据库
  postgres-primary:
    image: postgres:15
    environment:
      POSTGRES_DB: claude_memory
      POSTGRES_USER: claude_memory
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_primary_data:/var/lib/postgresql/data
      - ./config/postgres/postgresql.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf

  # PostgreSQL只读副本
  postgres-replica:
    image: postgres:15
    environment:
      PGUSER: replicator
      POSTGRES_PASSWORD: ${POSTGRES_REPLICA_PASSWORD}
    volumes:
      - postgres_replica_data:/var/lib/postgresql/data
    depends_on:
      - postgres-primary

  # Qdrant向量数据库集群
  qdrant-node1:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_node1_data:/qdrant/storage
    environment:
      QDRANT__CLUSTER__ENABLED: true
      QDRANT__CLUSTER__NODE_ID: 1

  qdrant-node2:
    image: qdrant/qdrant:latest
    ports:
      - "6334:6333"
    volumes:
      - qdrant_node2_data:/qdrant/storage
    environment:
      QDRANT__CLUSTER__ENABLED: true
      QDRANT__CLUSTER__NODE_ID: 2

  # Redis缓存集群
  redis-primary:
    image: redis:7
    command: redis-server --appendonly yes
    volumes:
      - redis_primary_data:/data

  redis-replica:
    image: redis:7
    command: redis-server --slaveof redis-primary 6379
    depends_on:
      - redis-primary
    volumes:
      - redis_replica_data:/data

  # Claude Memory MCP服务集群
  claude-memory-1:
    build:
      context: .
      dockerfile: Dockerfile.production
    environment:
      - DATABASE_URL=postgresql://claude_memory:${POSTGRES_PASSWORD}@postgres-primary:5432/claude_memory
      - QDRANT_URL=http://qdrant-node1:6333
      - REDIS_URL=redis://redis-primary:6379
      - SERVICE_ID=mcp-1
    depends_on:
      - postgres-primary
      - qdrant-node1
      - redis-primary

  claude-memory-2:
    build:
      context: .
      dockerfile: Dockerfile.production
    environment:
      - DATABASE_URL=postgresql://claude_memory:${POSTGRES_PASSWORD}@postgres-primary:5432/claude_memory
      - QDRANT_URL=http://qdrant-node2:6333
      - REDIS_URL=redis://redis-primary:6379
      - SERVICE_ID=mcp-2
    depends_on:
      - postgres-primary
      - qdrant-node2
      - redis-primary

  # Nginx负载均衡器
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - claude-memory-1
      - claude-memory-2

volumes:
  postgres_primary_data:
  postgres_replica_data:
  qdrant_node1_data:
  qdrant_node2_data:
  redis_primary_data:
  redis_replica_data:
```

### 4.3 负载均衡配置

```nginx
# config/nginx/nginx.conf
upstream claude_memory_backends {
    least_conn;
    server claude-memory-1:6334 max_fails=3 fail_timeout=30s;
    server claude-memory-2:6334 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name claude-memory.example.com;
    
    # 健康检查端点
    location /health {
        proxy_pass http://claude_memory_backends/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # MCP协议代理
    location /mcp {
        proxy_pass http://claude_memory_backends;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 4.4 监控配置

```yaml
# monitoring/docker-compose.monitoring.yml
version: '3.8'

services:
  # Prometheus监控
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  # Grafana仪表板
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources

  # AlertManager告警
  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml

volumes:
  prometheus_data:
  grafana_data:
```

### 4.5 部署自动化

```bash
#!/bin/bash
# deploy_production.sh - 生产环境部署脚本

set -e

# 配置变量
DEPLOY_ENV=${DEPLOY_ENV:-production}
VERSION=${VERSION:-latest}
BACKUP_DIR="/backups/claude-memory"

echo "🚀 开始Claude Memory MCP生产环境部署"
echo "环境: $DEPLOY_ENV"
echo "版本: $VERSION"

# 1. 准备部署环境
prepare_environment() {
    echo "📋 准备部署环境..."
    
    # 创建必要目录
    mkdir -p $BACKUP_DIR
    mkdir -p logs
    mkdir -p data
    
    # 设置权限
    chmod 750 data
    chmod 750 logs
    
    # 加载环境变量
    if [[ -f .env.$DEPLOY_ENV ]]; then
        source .env.$DEPLOY_ENV
    fi
}

# 2. 数据库备份
backup_database() {
    echo "💾 备份现有数据库..."
    
    if docker ps | grep -q postgres-primary; then
        docker exec postgres-primary pg_dump -U claude_memory claude_memory > \
            $BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql
        echo "✅ 数据库备份完成"
    fi
}

# 3. 拉取最新镜像
pull_images() {
    echo "📦 拉取最新Docker镜像..."
    docker-compose -f docker-compose.production.yml pull
}

# 4. 滚动更新
rolling_update() {
    echo "🔄 执行滚动更新..."
    
    # 更新服务1
    docker-compose -f docker-compose.production.yml up -d claude-memory-1
    sleep 30
    
    # 健康检查
    if ! curl -f http://localhost/health; then
        echo "❌ 服务1健康检查失败，回滚"
        return 1
    fi
    
    # 更新服务2
    docker-compose -f docker-compose.production.yml up -d claude-memory-2
    sleep 30
    
    # 最终健康检查
    if ! curl -f http://localhost/health; then
        echo "❌ 服务2健康检查失败，回滚"
        return 1
    fi
    
    echo "✅ 滚动更新完成"
}

# 5. 数据库迁移
migrate_database() {
    echo "🔧 执行数据库迁移..."
    
    docker exec claude-memory-1 python -c "
import asyncio
import sys
sys.path.insert(0, '/app/src')
from global_mcp.database_migrations import run_migrations

asyncio.run(run_migrations())
print('✅ 数据库迁移完成')
"
}

# 6. 部署验证
verify_deployment() {
    echo "🧪 验证部署..."
    
    # 健康检查
    if ! curl -f http://localhost/health; then
        echo "❌ 健康检查失败"
        return 1
    fi
    
    # MCP功能测试
    if ! docker exec claude-memory-1 python /app/test_mcp_service.py; then
        echo "❌ MCP功能测试失败"
        return 1
    fi
    
    echo "✅ 部署验证通过"
}

# 主部署流程
main() {
    prepare_environment
    backup_database
    pull_images
    
    if rolling_update; then
        migrate_database
        if verify_deployment; then
            echo "🎉 生产环境部署成功！"
        else
            echo "❌ 部署验证失败，建议回滚"
            exit 1
        fi
    else
        echo "❌ 滚动更新失败，开始回滚"
        # 这里可以添加回滚逻辑
        exit 1
    fi
}

# 执行部署
main "$@"
```

## 🔍 部署验证

### 完整验证脚本

```bash
#!/bin/bash
# verify_deployment.sh - 部署验证脚本

echo "🧪 Claude Memory MCP 部署验证"
echo "=============================="

# 1. 基础连接测试
echo "📡 测试基础连接..."
if curl -f http://localhost:6334/health > /dev/null 2>&1; then
    echo "✅ 服务连接正常"
else
    echo "❌ 服务连接失败"
    exit 1
fi

# 2. Claude CLI集成测试
echo "🔧 测试Claude CLI集成..."
if claude mcp list | grep -q claude-memory; then
    echo "✅ Claude CLI集成正常"
else
    echo "❌ Claude CLI集成失败"
    exit 1
fi

# 3. 功能测试
echo "⚡ 测试核心功能..."
if python test_mcp_service.py > /dev/null 2>&1; then
    echo "✅ 核心功能测试通过"
else
    echo "❌ 核心功能测试失败"
    exit 1
fi

# 4. 性能测试
echo "🚀 测试性能..."
if python test_concurrent_performance.py > /dev/null 2>&1; then
    echo "✅ 性能测试通过"
else
    echo "⚠️  性能测试警告"
fi

# 5. 跨平台兼容性
echo "🌐 测试跨平台兼容性..."
if python test_cross_platform.py > /dev/null 2>&1; then
    echo "✅ 跨平台兼容性测试通过"
else
    echo "⚠️  跨平台兼容性警告"
fi

echo ""
echo "🎉 部署验证完成！"
echo "系统已就绪，可以开始使用Claude Memory MCP服务。"
```

## 📊 监控和维护

### 日常监控检查项

1. **服务状态**: `docker ps` 或 `systemctl status claude-memory`
2. **健康检查**: `curl http://localhost:6334/health`
3. **日志监控**: `tail -f logs/claude_memory.log`
4. **性能指标**: 查看Grafana仪表板
5. **磁盘空间**: `df -h`
6. **内存使用**: `free -h`

### 定期维护任务

```bash
# 每日维护脚本
#!/bin/bash
# daily_maintenance.sh

# 日志轮转
find logs/ -name "*.log" -mtime +7 -delete

# 数据库清理
python scripts/cleanup_old_conversations.py --days 90

# 缓存清理
docker exec redis redis-cli FLUSHALL

# 健康检查报告
./verify_deployment.sh > reports/health_$(date +%Y%m%d).log
```

通过以上部署指南，您可以根据需求选择最适合的部署方式，从简单的开发环境到企业级生产环境，Claude Memory MCP都能稳定运行并提供优秀的性能。