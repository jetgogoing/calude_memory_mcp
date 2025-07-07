# Claude Memory MCP生产环境部署方案 v1.4

## 🎯 部署目标
- 在Ubuntu 22.04上建立企业级生产环境
- 实现高可用、高性能、可监控的MCP服务
- 建立完整的运维和监控体系

## 📋 部署清单

### 阶段1: 环境准备 (预计时间: 30分钟)

#### 1.1 系统要求验证
```bash
# 检查系统版本
lsb_release -a
# 检查资源
free -h && df -h
# 检查网络
curl -s https://api.github.com
```

**最低要求:**
- Ubuntu 22.04 LTS
- 8GB RAM (推荐16GB)
- 50GB可用存储
- Docker 24.0+, Docker Compose v2.20+

#### 1.2 基础依赖安装
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y curl wget git htop net-tools nginx certbot

# 安装Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 安装Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

### 阶段2: 数据库环境配置 (预计时间: 45分钟)

#### 2.1 PostgreSQL生产配置
```bash
# 安装PostgreSQL 15
sudo apt install -y postgresql-15 postgresql-contrib-15

# 配置数据库
sudo -u postgres createuser -d -r -s claude_memory
sudo -u postgres createdb -O claude_memory claude_memory_db

# 设置密码
sudo -u postgres psql -c "ALTER USER claude_memory PASSWORD 'your_secure_password';"

# 优化配置 /etc/postgresql/15/main/postgresql.conf
sudo tee -a /etc/postgresql/15/main/postgresql.conf << EOF
# 生产优化配置
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 256MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB
max_connections = 200
EOF

sudo systemctl restart postgresql
```

#### 2.2 Qdrant向量数据库部署
```bash
# 创建Qdrant目录
sudo mkdir -p /opt/qdrant/{data,logs,config}

# 下载Qdrant v1.7.4
cd /opt/qdrant
sudo wget https://github.com/qdrant/qdrant/releases/download/v1.7.4/qdrant-x86_64-unknown-linux-gnu.tar.gz
sudo tar -xzf qdrant-x86_64-unknown-linux-gnu.tar.gz
sudo chmod +x qdrant
sudo ln -s /opt/qdrant/qdrant /usr/local/bin/qdrant

# 生产配置文件
sudo tee /opt/qdrant/config/production.yaml << EOF
service:
  http_port: 6333
  grpc_port: 6334
  max_request_size_mb: 32
  max_workers: 4

storage:
  storage_path: /opt/qdrant/data
  optimizers:
    deleted_threshold: 0.2
    vacuum_min_vector_number: 1000
    default_segment_number: 0
    max_segment_size_kb: 2048000

cluster:
  enabled: false

telemetry:
  disabled: true
EOF

# 创建systemd服务
sudo tee /etc/systemd/system/qdrant.service << EOF
[Unit]
Description=Qdrant Vector Search Engine
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/qdrant --config-path /opt/qdrant/config/production.yaml
WorkingDirectory=/opt/qdrant
Restart=always
RestartSec=3
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable qdrant
sudo systemctl start qdrant
```

#### 2.3 Redis缓存配置
```bash
# 安装Redis
sudo apt install -y redis-server

# 生产配置 /etc/redis/redis.conf
sudo sed -i 's/^# maxmemory <bytes>/maxmemory 1gb/' /etc/redis/redis.conf
sudo sed -i 's/^# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf

sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

### 阶段3: 应用服务部署 (预计时间: 60分钟)

#### 3.1 代码部署和环境配置
```bash
# 部署目录
sudo mkdir -p /opt/claude-memory-mcp
sudo chown $USER:$USER /opt/claude-memory-mcp
cd /opt/claude-memory-mcp

# 复制项目文件(从当前开发环境)
cp -r /home/jetgogoing/claude_memory/* .

# 创建生产虚拟环境
python3.11 -m venv venv-production
source venv-production/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -e ".[dev]"

# 生产环境配置
cp .env .env.production
```

#### 3.2 生产环境配置文件
```bash
# 编辑生产配置
tee .env.production << EOF
# =====================================
# 生产环境配置
# =====================================

# 数据库配置
DATABASE_URL=postgresql://claude_memory:your_secure_password@localhost:5432/claude_memory_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Qdrant配置
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=claude_memory_vectors_v14
QDRANT_VECTOR_SIZE=4096

# API配置
SILICONFLOW_API_KEY=sk-tjjznxtevmlynypmydlhqepnatclvlrimsygimtyafdoxklw
GEMINI_API_KEY=AIzaSyDTBboAMDzVY7UMKK5gbNhwKufNTSDY0sw
OPENROUTER_API_KEY=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

# 应用配置
APP_DEBUG=false
APP_HOST=127.0.0.1
APP_PORT=8000

# 性能配置
PERFORMANCE_MAX_CONCURRENT_REQUESTS=20
PERFORMANCE_REQUEST_TIMEOUT_SECONDS=30

# 监控配置
MONITORING_ENABLE_METRICS=true
MONITORING_LOG_LEVEL=INFO
MONITORING_LOG_FILE_PATH=/var/log/claude-memory/service.log

# 成本控制
COST_DAILY_BUDGET_USD=0.5
COST_ENABLE_COST_ALERTS=true
EOF
```

#### 3.3 数据库初始化和迁移
```bash
# 初始化数据库
source venv-production/bin/activate
python scripts/init_database.py

# 执行v1.4数据迁移
python scripts/migrate_embeddings_v14.py --dry-run
python scripts/migrate_embeddings_v14.py

# 验证升级
python scripts/validate_v14_upgrade.py --full --performance
```

#### 3.4 完整MCP服务器配置
```bash
# 创建生产MCP服务器启动脚本
tee start_production_mcp.py << 'EOF'
#!/usr/bin/env python3
"""
生产环境Claude Memory MCP服务器启动脚本
"""

import asyncio
import os
import sys
import signal
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 设置生产环境
os.environ["ENV"] = "production"
os.environ["PYTHONPATH"] = str(Path(__file__).parent / "src")

# 加载生产配置
from dotenv import load_dotenv
load_dotenv(".env.production")

from claude_memory.mcp_server import ClaudeMemoryMCPServer
from claude_memory.config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

async def main():
    """启动生产MCP服务器"""
    settings = get_settings()
    
    logger.info("🚀 Starting Claude Memory MCP Server in Production Mode")
    logger.info(f"📊 Database: {settings.database.database_url}")
    logger.info(f"🔍 Qdrant: {settings.qdrant.qdrant_url}")
    logger.info(f"📈 Monitoring: {settings.monitoring.enable_metrics}")
    
    # 创建服务器实例
    server = ClaudeMemoryMCPServer()
    
    # 注册信号处理
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        asyncio.create_task(server.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 初始化服务器
        await server.initialize()
        logger.info("✅ Server initialized successfully")
        
        # 启动服务器
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await server.server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options={}
            )
            
    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")
        raise
    finally:
        logger.info("🛑 Server shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
EOF

chmod +x start_production_mcp.py
```

### 阶段4: 服务管理配置 (预计时间: 30分钟)

#### 4.1 Systemd服务配置
```bash
# 创建Claude Memory MCP服务
sudo tee /etc/systemd/system/claude-memory-mcp.service << EOF
[Unit]
Description=Claude Memory MCP Service
After=network.target postgresql.service qdrant.service redis-server.service
Wants=postgresql.service qdrant.service redis-server.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=/opt/claude-memory-mcp
ExecStart=/opt/claude-memory-mcp/venv-production/bin/python start_production_mcp.py
Restart=always
RestartSec=10
KillSignal=SIGTERM
TimeoutStopSec=30
LimitNOFILE=65536

# 环境变量
Environment=PYTHONPATH=/opt/claude-memory-mcp/src
Environment=ENV=production

# 日志配置
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 启用和启动服务
sudo systemctl daemon-reload
sudo systemctl enable claude-memory-mcp
sudo systemctl start claude-memory-mcp
```

#### 4.2 Claude CLI生产配置
```bash
# 更新Claude CLI配置
python3 << 'EOF'
import json
from pathlib import Path

claude_config_path = Path.home() / ".claude.json"
with open(claude_config_path, 'r') as f:
    config = json.load(f)

# 生产MCP配置
production_mcp_config = {
    "claude-memory-mcp": {
        "type": "stdio",
        "command": "/opt/claude-memory-mcp/venv-production/bin/python",
        "args": ["/opt/claude-memory-mcp/start_production_mcp.py"],
        "env": {
            "ENV": "production",
            "PYTHONPATH": "/opt/claude-memory-mcp/src"
        }
    }
}

# 更新全局配置
config["mcpServers"].update(production_mcp_config)

# 更新项目配置
project_path = "/opt/claude-memory-mcp"
if project_path not in config.get("projects", {}):
    config.setdefault("projects", {})[project_path] = {
        "allowedTools": [],
        "history": [],
        "mcpContextUris": [],
        "mcpServers": {},
        "enabledMcpjsonServers": [],
        "disabledMcpjsonServers": [],
        "hasTrustDialogAccepted": False,
        "projectOnboardingSeenCount": 0,
        "hasClaudeMdExternalIncludesApproved": False,
        "hasClaudeMdExternalIncludesWarningShown": False
    }

config["projects"][project_path]["mcpServers"] = production_mcp_config
config["projects"][project_path]["enabledMcpjsonServers"] = ["claude-memory-mcp"]

# 保存配置
with open(claude_config_path, 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("✅ Claude CLI生产配置已更新")
EOF
```

### 阶段5: 监控和运维配置 (预计时间: 45分钟)

#### 5.1 日志管理
```bash
# 创建日志目录
sudo mkdir -p /var/log/claude-memory
sudo chown $USER:$USER /var/log/claude-memory

# 配置logrotate
sudo tee /etc/logrotate.d/claude-memory << EOF
/var/log/claude-memory/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload claude-memory-mcp
    endscript
}
EOF
```

#### 5.2 监控栈部署
```bash
# 创建监控配置目录
mkdir -p /opt/claude-memory-mcp/monitoring/{prometheus,grafana}

# Prometheus配置
tee /opt/claude-memory-mcp/monitoring/prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'claude-memory-mcp'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: /metrics
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']
EOF

# Docker Compose监控栈
tee /opt/claude-memory-mcp/docker-compose.monitoring.yml << EOF
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: claude-memory-prometheus
    ports:
      - "9091:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.2.2
    container_name: claude-memory-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.6.1
    container_name: claude-memory-node-exporter
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    restart: unless-stopped

volumes:
  prometheus_data:
    driver: local
  grafana_data:
    driver: local
EOF

# 启动监控栈
docker-compose -f docker-compose.monitoring.yml up -d
```

#### 5.3 健康检查脚本
```bash
# 创建健康检查脚本
tee /opt/claude-memory-mcp/healthcheck.py << 'EOF'
#!/usr/bin/env python3
"""
Claude Memory MCP服务健康检查脚本
"""

import asyncio
import sys
import json
import time
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from claude_memory.config.settings import get_settings

async def check_services():
    """检查所有服务状态"""
    checks = []
    
    # 检查PostgreSQL
    try:
        result = subprocess.run(['pg_isready', '-h', 'localhost', '-p', '5432'], 
                              capture_output=True, timeout=5)
        checks.append({"service": "postgresql", "status": "healthy" if result.returncode == 0 else "unhealthy"})
    except Exception as e:
        checks.append({"service": "postgresql", "status": "error", "error": str(e)})
    
    # 检查Qdrant
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:6333/health", timeout=5)
            checks.append({"service": "qdrant", "status": "healthy" if response.status_code == 200 else "unhealthy"})
    except Exception as e:
        checks.append({"service": "qdrant", "status": "error", "error": str(e)})
    
    # 检查Redis
    try:
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, timeout=5)
        checks.append({"service": "redis", "status": "healthy" if result.stdout.strip() == b'PONG' else "unhealthy"})
    except Exception as e:
        checks.append({"service": "redis", "status": "error", "error": str(e)})
    
    # 检查MCP服务
    try:
        result = subprocess.run(['systemctl', 'is-active', 'claude-memory-mcp'], 
                              capture_output=True, timeout=5)
        checks.append({"service": "claude-memory-mcp", "status": "healthy" if result.stdout.strip() == b'active' else "unhealthy"})
    except Exception as e:
        checks.append({"service": "claude-memory-mcp", "status": "error", "error": str(e)})
    
    return checks

async def main():
    checks = await check_services()
    
    # 输出结果
    result = {
        "timestamp": time.time(),
        "checks": checks,
        "overall": "healthy" if all(c["status"] == "healthy" for c in checks) else "unhealthy"
    }
    
    print(json.dumps(result, indent=2))
    
    # 如果所有检查都通过，返回0，否则返回1
    sys.exit(0 if result["overall"] == "healthy" else 1)

if __name__ == "__main__":
    asyncio.run(main())
EOF

chmod +x /opt/claude-memory-mcp/healthcheck.py

# 添加crontab健康检查
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/claude-memory-mcp/venv-production/bin/python /opt/claude-memory-mcp/healthcheck.py >> /var/log/claude-memory/health.log 2>&1") | crontab -
```

### 阶段6: 安全配置 (预计时间: 30分钟)

#### 6.1 防火墙配置
```bash
# 配置UFW防火墙
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 允许必要端口
sudo ufw allow ssh
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 3000/tcp  # Grafana
sudo ufw allow 9091/tcp  # Prometheus

# 本地服务端口仅允许本地访问
sudo ufw allow from 127.0.0.1 to any port 5432  # PostgreSQL
sudo ufw allow from 127.0.0.1 to any port 6333  # Qdrant
sudo ufw allow from 127.0.0.1 to any port 6379  # Redis
sudo ufw allow from 127.0.0.1 to any port 8000  # MCP Service
```

#### 6.2 SSL/TLS配置
```bash
# 生成自签名证书用于开发测试
sudo mkdir -p /etc/ssl/claude-memory
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/claude-memory/private.key \
    -out /etc/ssl/claude-memory/certificate.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# 设置权限
sudo chmod 600 /etc/ssl/claude-memory/private.key
sudo chmod 644 /etc/ssl/claude-memory/certificate.crt
```

### 阶段7: 备份和恢复策略 (预计时间: 20分钟)

#### 7.1 数据备份脚本
```bash
# 创建备份脚本
tee /opt/claude-memory-mcp/backup.sh << 'EOF'
#!/bin/bash
"""
Claude Memory MCP数据备份脚本
"""

BACKUP_DIR="/opt/claude-memory-mcp/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="claude_memory_db"
DB_USER="claude_memory"

# 创建备份目录
mkdir -p $BACKUP_DIR

# PostgreSQL备份
pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Qdrant数据备份
tar -czf $BACKUP_DIR/qdrant_$DATE.tar.gz -C /opt/qdrant data/

# 配置文件备份
tar -czf $BACKUP_DIR/config_$DATE.tar.gz .env.production /opt/claude-memory-mcp/src/claude_memory/config/

# 清理7天前的备份
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete

echo "✅ Backup completed: $DATE"
EOF

chmod +x /opt/claude-memory-mcp/backup.sh

# 添加定时备份
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/claude-memory-mcp/backup.sh >> /var/log/claude-memory/backup.log 2>&1") | crontab -
```

## 🚀 部署执行和验证

### 验证部署成功
```bash
# 检查所有服务状态
sudo systemctl status postgresql qdrant redis-server claude-memory-mcp

# 验证MCP服务健康
/opt/claude-memory-mcp/venv-production/bin/python /opt/claude-memory-mcp/healthcheck.py

# 测试Claude CLI集成
claude  # 重启Claude CLI
# 在Claude CLI中执行: /mcp
# 应该看到claude-memory-mcp服务状态为 ✅ ready
```

### 性能测试
```bash
# 运行集成测试
cd /opt/claude-memory-mcp
source venv-production/bin/activate
python scripts/test_mcp_integration.py

# 运行性能验证
python scripts/validate_v14_upgrade.py --performance
```

### 监控访问
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9091
- **健康检查**: `/opt/claude-memory-mcp/healthcheck.py`

## 📊 生产运维清单

### 日常运维任务
- [ ] 每日检查服务日志: `journalctl -u claude-memory-mcp -f`
- [ ] 每周检查磁盘空间: `df -h`
- [ ] 每月检查备份完整性
- [ ] 每季度更新依赖包: `pip list --outdated`

### 故障排除指南
1. **MCP连接失败**: 检查systemctl status claude-memory-mcp
2. **数据库连接问题**: 检查PostgreSQL服务和连接字符串
3. **向量搜索异常**: 检查Qdrant服务状态
4. **内存/CPU过高**: 检查Prometheus监控指标

### 扩展配置
- **负载均衡**: 使用Nginx upstream配置多实例
- **高可用**: 配置PostgreSQL主从复制
- **自动扩缩**: 基于CPU/内存指标的自动扩容

---

## 🎯 预期结果

部署完成后，您将拥有：
- ✅ **生产级MCP服务**: 完整功能，高性能，可监控
- ✅ **完整监控体系**: Prometheus + Grafana仪表板
- ✅ **自动化运维**: 健康检查，自动备份，日志轮转
- ✅ **安全防护**: 防火墙，SSL证书，权限控制
- ✅ **灾备方案**: 定期备份，快速恢复流程

**成本目标**: 日运行成本 $0.3-0.5 (API调用)
**性能指标**: 
- 语义检索延迟 ≤ 150ms
- 端到端处理延迟 ≤ 300ms  
- 服务可用性 ≥ 99.5%