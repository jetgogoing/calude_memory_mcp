#!/bin/bash

# Claude Memory MCP Service - Ubuntu 22.04 生产部署脚本
# 此脚本自动化部署流程，减少手动操作错误

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
INSTALL_DIR="/opt/claude-memory"
APP_USER="claude-memory"
BACKUP_DIR="/backup/claude-memory"
LOG_DIR="/var/log/claude-memory"

# 打印函数
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为 root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "此脚本必须以 root 权限运行"
        exit 1
    fi
}

# 检查系统版本
check_system() {
    if ! grep -q "Ubuntu 22.04" /etc/os-release; then
        print_warning "此脚本针对 Ubuntu 22.04 优化，其他版本可能需要调整"
        read -p "是否继续？(y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 安装基础依赖
install_dependencies() {
    print_info "安装系统依赖..."
    
    apt update
    apt upgrade -y
    
    apt install -y \
        curl wget git vim htop \
        build-essential software-properties-common \
        ca-certificates gnupg lsb-release \
        net-tools ufw fail2ban \
        python3.10 python3.10-venv python3-pip \
        postgresql-14 postgresql-contrib \
        redis-server nginx supervisor \
        certbot python3-certbot-nginx
    
    # 安装 Docker
    if ! command -v docker &> /dev/null; then
        print_info "安装 Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
    fi
    
    print_success "依赖安装完成"
}

# 创建用户和目录
setup_user_and_dirs() {
    print_info "创建用户和目录结构..."
    
    # 创建用户
    if ! id "$APP_USER" &>/dev/null; then
        useradd -m -s /bin/bash $APP_USER
        usermod -aG sudo,docker $APP_USER
    fi
    
    # 创建目录
    mkdir -p $INSTALL_DIR
    mkdir -p $LOG_DIR
    mkdir -p $BACKUP_DIR/{postgres,qdrant,configs}
    mkdir -p /var/run/claude-memory
    
    # 设置权限
    chown -R $APP_USER:$APP_USER $INSTALL_DIR
    chown -R $APP_USER:$APP_USER $LOG_DIR
    chown -R $APP_USER:$APP_USER /var/run/claude-memory
    
    print_success "用户和目录创建完成"
}

# 系统优化
optimize_system() {
    print_info "优化系统参数..."
    
    # 内核参数优化
    cat > /etc/sysctl.d/99-claude-memory.conf << EOF
# 网络优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.ip_local_port_range = 1024 65535

# 文件描述符
fs.file-max = 1000000
fs.nr_open = 1000000

# 内存优化
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
EOF
    
    sysctl -p /etc/sysctl.d/99-claude-memory.conf
    
    # ulimit 设置
    cat > /etc/security/limits.d/claude-memory.conf << EOF
$APP_USER soft nofile 65535
$APP_USER hard nofile 65535
$APP_USER soft nproc 65535
$APP_USER hard nproc 65535
EOF
    
    print_success "系统优化完成"
}

# 配置 PostgreSQL
setup_postgresql() {
    print_info "配置 PostgreSQL..."
    
    # 生成随机密码
    DB_PASSWORD=$(openssl rand -base64 32)
    
    # 创建数据库和用户
    sudo -u postgres psql << EOF
CREATE USER claude_memory WITH PASSWORD '$DB_PASSWORD';
CREATE DATABASE claude_memory OWNER claude_memory;
GRANT ALL PRIVILEGES ON DATABASE claude_memory TO claude_memory;
EOF
    
    # 保存密码
    echo "DATABASE_PASSWORD=$DB_PASSWORD" > $INSTALL_DIR/.db_password
    chmod 600 $INSTALL_DIR/.db_password
    chown $APP_USER:$APP_USER $INSTALL_DIR/.db_password
    
    # 配置 PostgreSQL
    PG_VERSION=$(ls /etc/postgresql/)
    PG_CONFIG="/etc/postgresql/$PG_VERSION/main/postgresql.conf"
    
    # 备份原配置
    cp $PG_CONFIG ${PG_CONFIG}.backup
    
    # 优化配置
    cat >> $PG_CONFIG << EOF

# Claude Memory 优化配置
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4
EOF
    
    systemctl restart postgresql
    
    print_success "PostgreSQL 配置完成"
}

# 配置 Redis
setup_redis() {
    print_info "配置 Redis..."
    
    # 生成 Redis 密码
    REDIS_PASSWORD=$(openssl rand -base64 32)
    
    # 备份原配置
    cp /etc/redis/redis.conf /etc/redis/redis.conf.backup
    
    # 修改配置
    sed -i "s/^# requirepass .*/requirepass $REDIS_PASSWORD/" /etc/redis/redis.conf
    sed -i "s/^bind .*/bind 127.0.0.1/" /etc/redis/redis.conf
    sed -i "s/^# maxmemory .*/maxmemory 1gb/" /etc/redis/redis.conf
    sed -i "s/^# maxmemory-policy .*/maxmemory-policy allkeys-lru/" /etc/redis/redis.conf
    
    # 保存密码
    echo "REDIS_PASSWORD=$REDIS_PASSWORD" >> $INSTALL_DIR/.db_password
    
    systemctl restart redis-server
    
    print_success "Redis 配置完成"
}

# 部署 Qdrant
setup_qdrant() {
    print_info "部署 Qdrant..."
    
    # 创建存储目录
    mkdir -p $INSTALL_DIR/qdrant/storage
    chown -R $APP_USER:$APP_USER $INSTALL_DIR/qdrant
    
    # 启动 Qdrant
    docker run -d \
        --name qdrant \
        --restart unless-stopped \
        -p 6333:6333 \
        -p 6334:6334 \
        -v $INSTALL_DIR/qdrant/storage:/qdrant/storage \
        -e QDRANT__SERVICE__HTTP_PORT=6333 \
        -e QDRANT__SERVICE__GRPC_PORT=6334 \
        -e QDRANT__LOG_LEVEL=INFO \
        qdrant/qdrant:v1.11.0
    
    # 等待启动
    sleep 10
    
    # 检查状态
    if curl -s http://localhost:6333 > /dev/null; then
        print_success "Qdrant 部署成功"
    else
        print_error "Qdrant 部署失败"
        exit 1
    fi
}

# 部署应用
deploy_application() {
    print_info "部署应用代码..."
    
    # 切换到应用用户
    sudo -u $APP_USER bash << EOF
cd $INSTALL_DIR

# 克隆代码（如果不存在）
if [ ! -d "app" ]; then
    git clone https://github.com/your-repo/claude-memory.git app
fi

cd app

# 创建虚拟环境
python3.10 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn uvloop httptools

# 创建生产配置
cp .env.example .env.production
EOF
    
    # 获取数据库密码
    source $INSTALL_DIR/.db_password
    
    # 更新配置文件
    cat > $INSTALL_DIR/app/.env.production << EOF
# 数据库配置
DATABASE_URL=postgresql://claude_memory:$DATABASE_PASSWORD@localhost:5432/claude_memory
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://:$REDIS_PASSWORD@localhost:6379/0

# API 密钥（需要手动填写）
SILICONFLOW_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=

# 应用配置
APP_ENV=production
APP_DEBUG=false
APP_LOG_LEVEL=INFO

# 性能配置
PERFORMANCE_MAX_WORKERS=4
PERFORMANCE_MAX_CONCURRENT_REQUESTS=100
PERFORMANCE_REQUEST_TIMEOUT_SECONDS=30
PERFORMANCE_CACHE_TTL_SECONDS=3600
PERFORMANCE_RESPONSE_CACHE_SIZE=500

# 监控配置
MONITORING_LOG_LEVEL=INFO
MONITORING_ENABLE_METRICS=true
EOF
    
    chown $APP_USER:$APP_USER $INSTALL_DIR/app/.env.production
    chmod 600 $INSTALL_DIR/app/.env.production
    
    print_success "应用部署完成"
    print_warning "请编辑 $INSTALL_DIR/app/.env.production 添加 API 密钥"
}

# 创建 Gunicorn 配置
create_gunicorn_config() {
    print_info "创建 Gunicorn 配置..."
    
    cat > $INSTALL_DIR/app/gunicorn_config.py << 'EOF'
import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/claude-memory/access.log"
errorlog = "/var/log/claude-memory/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'claude-memory-mcp'

# Server mechanics
daemon = False
pidfile = '/var/run/claude-memory/gunicorn.pid'
user = 'claude-memory'
group = 'claude-memory'
tmp_upload_dir = None
EOF
    
    chown $APP_USER:$APP_USER $INSTALL_DIR/app/gunicorn_config.py
    
    print_success "Gunicorn 配置创建完成"
}

# 创建 Systemd 服务
create_systemd_service() {
    print_info "创建 Systemd 服务..."
    
    cat > /etc/systemd/system/claude-memory.service << EOF
[Unit]
Description=Claude Memory MCP Service
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=notify
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR/app
Environment="PATH=$INSTALL_DIR/app/venv/bin"
Environment="PYTHONPATH=$INSTALL_DIR/app"
EnvironmentFile=$INSTALL_DIR/app/.env.production

ExecStart=$INSTALL_DIR/app/venv/bin/gunicorn \\
    --config $INSTALL_DIR/app/gunicorn_config.py \\
    src.claude_memory.mcp_server:app

ExecReload=/bin/kill -s HUP \$MAINPID
ExecStop=/bin/kill -s TERM \$MAINPID

Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# 资源限制
LimitNOFILE=65535
LimitNPROC=65535

# 安全设置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$LOG_DIR $INSTALL_DIR/app

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    
    print_success "Systemd 服务创建完成"
}

# 配置 Nginx
setup_nginx() {
    print_info "配置 Nginx..."
    
    # 获取域名
    read -p "请输入域名（例如：api.example.com）: " DOMAIN_NAME
    
    # 创建 Nginx 配置
    cat > /etc/nginx/sites-available/claude-memory << EOF
upstream claude_memory_backend {
    least_conn;
    server 127.0.0.1:8000 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 80;
    server_name $DOMAIN_NAME;
    
    location / {
        proxy_pass http://claude_memory_backend;
        proxy_http_version 1.1;
        
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    location /health {
        proxy_pass http://claude_memory_backend;
        access_log off;
    }
}
EOF
    
    # 启用站点
    ln -sf /etc/nginx/sites-available/claude-memory /etc/nginx/sites-enabled/
    
    # 测试配置
    nginx -t
    
    systemctl restart nginx
    
    print_success "Nginx 配置完成"
    print_info "可以使用 certbot --nginx -d $DOMAIN_NAME 配置 SSL"
}

# 配置防火墙
setup_firewall() {
    print_info "配置防火墙..."
    
    # 基本规则
    ufw default deny incoming
    ufw default allow outgoing
    
    # 允许 SSH
    ufw allow 22/tcp
    
    # 允许 HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # 启用防火墙
    echo "y" | ufw enable
    
    print_success "防火墙配置完成"
}

# 创建维护脚本
create_maintenance_scripts() {
    print_info "创建维护脚本..."
    
    # 健康检查脚本
    cat > $INSTALL_DIR/scripts/health_check.sh << 'EOF'
#!/bin/bash

check_service() {
    local service=$1
    if systemctl is-active --quiet $service; then
        echo "✓ $service is running"
        return 0
    else
        echo "✗ $service is not running"
        return 1
    fi
}

check_port() {
    local port=$1
    local service=$2
    if ss -tuln | grep -q ":$port "; then
        echo "✓ $service port $port is open"
        return 0
    else
        echo "✗ $service port $port is not open"
        return 1
    fi
}

echo "=== Claude Memory Health Check ==="
echo "Time: $(date)"
echo ""

check_service postgresql
check_service redis-server
check_service claude-memory
check_service nginx

echo ""
check_port 5432 PostgreSQL
check_port 6379 Redis
check_port 6333 Qdrant
check_port 8000 "MCP Service"

echo ""
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q 200; then
    echo "✓ API health check passed"
else
    echo "✗ API health check failed"
fi
EOF
    
    chmod +x $INSTALL_DIR/scripts/health_check.sh
    
    # 备份脚本
    cat > $INSTALL_DIR/scripts/backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/backup/claude-memory"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR/{postgres,qdrant,configs}

echo "Starting backup..."

# PostgreSQL
sudo -u postgres pg_dump claude_memory | gzip > $BACKUP_DIR/postgres/claude_memory_$DATE.sql.gz

# Qdrant
docker exec qdrant qdrant-backup create /qdrant/backups/backup_$DATE

# Configs
tar -czf $BACKUP_DIR/configs/configs_$DATE.tar.gz \
    /opt/claude-memory/app/.env.production \
    /etc/nginx/sites-available/claude-memory

echo "Backup completed: $DATE"
EOF
    
    chmod +x $INSTALL_DIR/scripts/backup.sh
    
    print_success "维护脚本创建完成"
}

# 初始化数据库
init_database() {
    print_info "初始化数据库..."
    
    sudo -u $APP_USER bash << EOF
cd $INSTALL_DIR/app
source venv/bin/activate
python scripts/init_database_tables.py
EOF
    
    print_success "数据库初始化完成"
}

# 启动服务
start_services() {
    print_info "启动服务..."
    
    systemctl enable claude-memory
    systemctl start claude-memory
    
    sleep 5
    
    # 检查服务状态
    if systemctl is-active --quiet claude-memory; then
        print_success "Claude Memory 服务启动成功"
    else
        print_error "Claude Memory 服务启动失败"
        journalctl -u claude-memory -n 50
        exit 1
    fi
}

# 显示部署信息
show_deployment_info() {
    source $INSTALL_DIR/.db_password
    
    echo ""
    echo "========================================"
    echo "Claude Memory MCP Service 部署完成！"
    echo "========================================"
    echo ""
    echo "重要信息："
    echo "- 安装目录: $INSTALL_DIR"
    echo "- 日志目录: $LOG_DIR"
    echo "- 备份目录: $BACKUP_DIR"
    echo ""
    echo "数据库密码已保存到: $INSTALL_DIR/.db_password"
    echo ""
    echo "下一步操作："
    echo "1. 编辑 $INSTALL_DIR/app/.env.production 添加 API 密钥"
    echo "2. 重启服务: systemctl restart claude-memory"
    echo "3. 配置 SSL: certbot --nginx -d your-domain.com"
    echo "4. 运行健康检查: $INSTALL_DIR/scripts/health_check.sh"
    echo ""
    echo "常用命令："
    echo "- 查看日志: journalctl -u claude-memory -f"
    echo "- 查看状态: systemctl status claude-memory"
    echo "- 重启服务: systemctl restart claude-memory"
    echo "- 备份数据: $INSTALL_DIR/scripts/backup.sh"
    echo ""
}

# 主函数
main() {
    print_info "开始部署 Claude Memory MCP Service..."
    
    check_root
    check_system
    
    install_dependencies
    setup_user_and_dirs
    optimize_system
    setup_postgresql
    setup_redis
    setup_qdrant
    deploy_application
    create_gunicorn_config
    create_systemd_service
    setup_nginx
    setup_firewall
    create_maintenance_scripts
    init_database
    start_services
    
    show_deployment_info
}

# 运行主函数
main