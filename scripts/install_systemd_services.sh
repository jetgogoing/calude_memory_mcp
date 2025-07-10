#!/bin/bash
# 安装 systemd 服务以实现真正的自动启动
# 运行此脚本需要 sudo 权限

set -e

echo "🔧 安装 Claude Memory 系统服务..."

PROJECT_ROOT="/home/jetgogoing/claude_memory"
SERVICE_USER="jetgogoing"

# 1. 创建 Qdrant 服务
cat > /tmp/claude-memory-qdrant.service << EOF
[Unit]
Description=Claude Memory Qdrant Vector Database
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_ROOT
ExecStart=$PROJECT_ROOT/scripts/start_qdrant.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 2. 创建 API Server 服务
cat > /tmp/claude-memory-api.service << EOF
[Unit]
Description=Claude Memory API Server
After=network.target postgresql.service claude-memory-qdrant.service
Requires=postgresql.service claude-memory-qdrant.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_ROOT
Environment="PYTHONPATH=$PROJECT_ROOT/src"
EnvironmentFile=$PROJECT_ROOT/.env
ExecStart=$PROJECT_ROOT/venv/bin/python -m claude_memory.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 3. 创建对话采集器服务
cat > /tmp/claude-memory-collector.service << EOF
[Unit]
Description=Claude Memory Conversation Collector
After=network.target claude-memory-api.service
Requires=claude-memory-api.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_ROOT
Environment="PYTHONPATH=$PROJECT_ROOT/src"
EnvironmentFile=$PROJECT_ROOT/.env
ExecStart=$PROJECT_ROOT/venv/bin/python $PROJECT_ROOT/scripts/start_collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 4. 安装服务文件
echo "📦 安装服务文件..."
sudo cp /tmp/claude-memory-*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 5. 启用服务自动启动
echo "🚀 启用自动启动..."
sudo systemctl enable claude-memory-qdrant.service
sudo systemctl enable claude-memory-api.service
sudo systemctl enable claude-memory-collector.service

# 6. 启动服务
echo "▶️  启动服务..."
sudo systemctl start claude-memory-qdrant.service
sleep 5
sudo systemctl start claude-memory-api.service
sleep 3
sudo systemctl start claude-memory-collector.service

# 7. 检查服务状态
echo ""
echo "✅ 服务安装完成！当前状态："
echo ""
sudo systemctl status claude-memory-qdrant.service --no-pager | head -n 3
sudo systemctl status claude-memory-api.service --no-pager | head -n 3
sudo systemctl status claude-memory-collector.service --no-pager | head -n 3

echo ""
echo "📌 有用的命令："
echo "  查看日志: sudo journalctl -u claude-memory-api -f"
echo "  重启服务: sudo systemctl restart claude-memory-api"
echo "  停止服务: sudo systemctl stop claude-memory-api"
echo ""
echo "现在，每次系统启动时，Claude Memory 服务都会自动启动！"