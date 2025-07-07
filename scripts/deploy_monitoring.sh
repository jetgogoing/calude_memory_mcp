#!/bin/bash
#
# Claude Memory监控系统部署脚本
# 安装配置Prometheus + Alertmanager + Webhook
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_ROOT="/home/jetgogoing/claude_memory"
CONFIG_DIR="$PROJECT_ROOT/config"
DATA_DIR="$PROJECT_ROOT/data"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"

echo -e "${BLUE}🚀 开始部署Claude Memory监控系统...${NC}"

# 1. 创建必要目录
echo -e "${YELLOW}📁 创建数据目录...${NC}"
mkdir -p "$DATA_DIR/prometheus"
mkdir -p "$DATA_DIR/alertmanager"
mkdir -p "$PROJECT_ROOT/logs"

# 2. 下载Prometheus (如果不存在)
if [ ! -f "/usr/local/bin/prometheus" ]; then
    echo -e "${YELLOW}📥 下载Prometheus...${NC}"
    cd /tmp
    PROMETHEUS_VERSION="2.45.0"
    wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz"
    tar xzf "prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz"
    sudo cp "prometheus-${PROMETHEUS_VERSION}.linux-amd64/prometheus" /usr/local/bin/
    sudo cp "prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool" /usr/local/bin/
    sudo chmod +x /usr/local/bin/prometheus
    sudo chmod +x /usr/local/bin/promtool
    rm -rf "prometheus-${PROMETHEUS_VERSION}.linux-amd64"*
    echo -e "${GREEN}✅ Prometheus安装完成${NC}"
else
    echo -e "${GREEN}✅ Prometheus已安装${NC}"
fi

# 3. 下载Alertmanager (如果不存在)
if [ ! -f "/usr/local/bin/alertmanager" ]; then
    echo -e "${YELLOW}📥 下载Alertmanager...${NC}"
    cd /tmp
    ALERTMANAGER_VERSION="0.25.0"
    wget -q "https://github.com/prometheus/alertmanager/releases/download/v${ALERTMANAGER_VERSION}/alertmanager-${ALERTMANAGER_VERSION}.linux-amd64.tar.gz"
    tar xzf "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64.tar.gz"
    sudo cp "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64/alertmanager" /usr/local/bin/
    sudo cp "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64/amtool" /usr/local/bin/
    sudo chmod +x /usr/local/bin/alertmanager
    sudo chmod +x /usr/local/bin/amtool
    rm -rf "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64"*
    echo -e "${GREEN}✅ Alertmanager安装完成${NC}"
else
    echo -e "${GREEN}✅ Alertmanager已安装${NC}"
fi

# 4. 安装systemd服务
echo -e "${YELLOW}📝 安装systemd服务...${NC}"

# 复制服务文件
sudo cp "$CONFIG_DIR/systemd/prometheus.service" "/etc/systemd/system/"
sudo cp "$CONFIG_DIR/systemd/alertmanager.service" "/etc/systemd/system/"
sudo cp "$CONFIG_DIR/systemd/claude-memory-webhook.service" "/etc/systemd/system/"

# 重新加载systemd
sudo systemctl daemon-reload

# 5. 验证配置文件
echo -e "${YELLOW}🔍 验证配置文件...${NC}"

# 验证Prometheus配置
if /usr/local/bin/promtool check config "$CONFIG_DIR/prometheus.yml"; then
    echo -e "${GREEN}✅ Prometheus配置文件有效${NC}"
else
    echo -e "${RED}❌ Prometheus配置文件无效${NC}"
    exit 1
fi

# 验证告警规则
if /usr/local/bin/promtool check rules "$CONFIG_DIR/claude_memory_alerts.yml"; then
    echo -e "${GREEN}✅ 告警规则文件有效${NC}"
else
    echo -e "${RED}❌ 告警规则文件无效${NC}"
    exit 1
fi

# 验证Alertmanager配置
if /usr/local/bin/amtool config check "$CONFIG_DIR/alertmanager.yml"; then
    echo -e "${GREEN}✅ Alertmanager配置文件有效${NC}"
else
    echo -e "${RED}❌ Alertmanager配置文件无效${NC}"
    exit 1
fi

# 6. 设置权限
echo -e "${YELLOW}🔐 设置权限...${NC}"
sudo chown -R jetgogoing:jetgogoing "$PROJECT_ROOT/data"
sudo chown -R jetgogoing:jetgogoing "$PROJECT_ROOT/logs"
chmod +x "$SCRIPTS_DIR/alert_webhook.py"

# 7. 启动服务
echo -e "${YELLOW}🔄 启动监控服务...${NC}"

# 启动Prometheus
sudo systemctl enable prometheus
sudo systemctl start prometheus
echo -e "${GREEN}✅ Prometheus服务已启动${NC}"

# 启动Alertmanager
sudo systemctl enable alertmanager
sudo systemctl start alertmanager
echo -e "${GREEN}✅ Alertmanager服务已启动${NC}"

# 启动Webhook服务
sudo systemctl enable claude-memory-webhook
sudo systemctl start claude-memory-webhook
echo -e "${GREEN}✅ 告警Webhook服务已启动${NC}"

# 8. 等待服务启动
echo -e "${YELLOW}⏳ 等待服务启动...${NC}"
sleep 5

# 9. 验证服务状态
echo -e "${YELLOW}🔍 验证服务状态...${NC}"

check_service() {
    local service_name=$1
    local port=$2
    local endpoint=$3
    
    if sudo systemctl is-active --quiet "$service_name"; then
        echo -e "${GREEN}✅ $service_name 服务运行中${NC}"
        
        if curl -s "http://localhost:$port$endpoint" > /dev/null; then
            echo -e "${GREEN}✅ $service_name HTTP接口正常${NC}"
        else
            echo -e "${YELLOW}⚠️ $service_name HTTP接口可能未就绪${NC}"
        fi
    else
        echo -e "${RED}❌ $service_name 服务未运行${NC}"
        sudo systemctl status "$service_name" --no-pager -l
    fi
}

check_service "prometheus" "9090" "/-/healthy"
check_service "alertmanager" "9093" "/-/healthy"
check_service "claude-memory-webhook" "8081" "/webhook"

# 10. 显示访问信息
echo -e "\n${BLUE}📊 监控系统访问信息:${NC}"
echo -e "${GREEN}🔗 Prometheus: http://localhost:9090${NC}"
echo -e "${GREEN}🔗 Alertmanager: http://localhost:9093${NC}"
echo -e "${GREEN}🔗 Claude Memory指标: http://localhost:8080/metrics${NC}"
echo -e "${GREEN}🔗 Claude Memory健康检查: http://localhost:8080/health${NC}"

# 11. 显示有用命令
echo -e "\n${BLUE}📋 有用命令:${NC}"
echo -e "${YELLOW}查看服务状态:${NC}"
echo "  sudo systemctl status prometheus"
echo "  sudo systemctl status alertmanager"
echo "  sudo systemctl status claude-memory-webhook"

echo -e "\n${YELLOW}查看日志:${NC}"
echo "  sudo journalctl -u prometheus -f"
echo "  sudo journalctl -u alertmanager -f"
echo "  sudo journalctl -u claude-memory-webhook -f"
echo "  tail -f $PROJECT_ROOT/logs/alerts.log"

echo -e "\n${YELLOW}重新加载配置:${NC}"
echo "  sudo systemctl reload prometheus"
echo "  sudo systemctl reload alertmanager"

echo -e "\n${GREEN}🎉 Claude Memory监控系统部署完成！${NC}"

# 12. 创建快速管理脚本
cat > "$SCRIPTS_DIR/monitoring_control.sh" << 'EOF'
#!/bin/bash
# Claude Memory监控系统控制脚本

case "$1" in
    start)
        echo "🚀 启动监控服务..."
        sudo systemctl start prometheus alertmanager claude-memory-webhook
        ;;
    stop)
        echo "🛑 停止监控服务..."
        sudo systemctl stop prometheus alertmanager claude-memory-webhook
        ;;
    restart)
        echo "🔄 重启监控服务..."
        sudo systemctl restart prometheus alertmanager claude-memory-webhook
        ;;
    status)
        echo "📊 监控服务状态:"
        sudo systemctl status prometheus alertmanager claude-memory-webhook --no-pager
        ;;
    logs)
        echo "📋 查看监控日志:"
        sudo journalctl -u prometheus -u alertmanager -u claude-memory-webhook -f
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
EOF

chmod +x "$SCRIPTS_DIR/monitoring_control.sh"
echo -e "${GREEN}✅ 监控控制脚本创建: $SCRIPTS_DIR/monitoring_control.sh${NC}"