# Claude Memory 快速参考卡

> **用途**: 常用命令、端口、路径等重要信息速查  
> **版本**: 1.4.0-monitoring

## 🚀 快速启动

```bash
# 检查所有服务状态
./scripts/monitoring_control.sh status

# 启动所有监控服务
./scripts/monitoring_control.sh start

# 测试MCP连接
python3 scripts/test_mcp_integration.py

# 生成监控报告
python3 scripts/cost_capacity_monitor.py
```

## 🌐 重要端点

| 服务 | 端口 | URL | 用途 |
|------|------|-----|------|
| MCP指标 | 8080 | http://localhost:8080/metrics | Prometheus指标 |
| MCP健康 | 8080 | http://localhost:8080/health | 健康检查API |
| Prometheus | 9090 | http://localhost:9090 | 监控界面 |
| Alertmanager | 9093 | http://localhost:9093 | 告警管理 |
| PostgreSQL | 5432 | localhost:5432 | 主数据库 |
| Qdrant | 6333 | http://localhost:6333 | 向量数据库 |
| Webhook | 8081 | http://localhost:8081/webhook | 告警接收 |

## 📁 重要路径

| 类型 | 路径 | 说明 |
|------|------|------|
| 项目根目录 | `/home/jetgogoing/claude_memory` | 主目录 |
| 配置文件 | `config/` | 所有配置文件 |
| 脚本目录 | `scripts/` | 管理脚本 |
| 日志目录 | `logs/` | 所有日志文件 |
| 报告目录 | `reports/` | 监控报告 |
| 备份目录 | `backups/` | 数据备份 |
| 文档目录 | `docs/` | 项目文档 |
| 数据目录 | `data/` | 数据库文件 |

## 📋 服务管理

### Systemd服务

```bash
# MCP服务 (监控版)
sudo systemctl {start|stop|restart|status} claude-memory-mcp-monitoring

# 监控服务
sudo systemctl {start|stop|restart|status} prometheus
sudo systemctl {start|stop|restart|status} alertmanager  
sudo systemctl {start|stop|restart|status} claude-memory-webhook

# 数据库服务
sudo systemctl {start|stop|restart|status} postgresql
sudo systemctl {start|stop|restart|status} qdrant
```

### 服务控制脚本

```bash
# 统一监控服务控制
./scripts/monitoring_control.sh {start|stop|restart|status|logs}

# MCP服务启动
python3 scripts/start_mcp_service.py

# 重启Claude CLI
python3 scripts/restart_claude_cli.py
```

## 🔍 健康检查

### 快速检查命令

```bash
# 服务状态
curl http://localhost:8080/health
curl http://localhost:9090/-/healthy  
curl http://localhost:9093/-/healthy

# 数据库连接
psql -h localhost -U claude_memory -d claude_memory_db -c "SELECT 1;"
curl http://localhost:6333/cluster

# 系统资源
df -h && free -h && top -bn1 | head -5
```

### MCP功能测试

```bash
# 通过Claude CLI测试
/mcp claude-memory ping
/mcp claude-memory memory_health
/mcp claude-memory memory_search query="test"

# 直接脚本测试
python3 scripts/test_mcp_integration.py
```

## 📊 监控查看

### Prometheus查询

访问 http://localhost:9090/graph 查询：

```prometheus
# 服务运行时间
claude_memory_uptime_seconds

# 请求总数
claude_memory_requests_total

# 服务状态
claude_memory_postgres_up
claude_memory_qdrant_up

# 响应时间
claude_memory_avg_response_time_seconds
```

### 告警查看

```bash
# 查看告警日志
tail -f logs/alerts.log

# 查看Alertmanager状态
curl http://localhost:9093/api/v1/alerts

# 测试告警
curl -X POST http://localhost:8081/webhook \
  -H "Content-Type: application/json" \
  -d '{"alerts":[{"status":"firing","labels":{"alertname":"test"}}]}'
```

## 📝 日志文件

| 服务 | 日志路径 | 查看命令 |
|------|----------|----------|
| MCP服务器 | `logs/monitoring_mcp.log` | `tail -f logs/monitoring_mcp.log` |
| 告警处理 | `logs/alerts.log` | `tail -f logs/alerts.log` |
| Cron任务 | `logs/cron.log` | `tail -f logs/cron.log` |
| 周度分析 | `logs/weekly_analysis.log` | `tail -f logs/weekly_analysis.log` |
| 数据维护 | `logs/maintenance.log` | `tail -f logs/maintenance.log` |
| 备份任务 | `logs/backup.log` | `tail -f logs/backup.log` |
| Prometheus | systemd | `sudo journalctl -u prometheus -f` |
| Alertmanager | systemd | `sudo journalctl -u alertmanager -f` |
| PostgreSQL | `/var/log/postgresql/` | `sudo tail -f /var/log/postgresql/postgresql-*.log` |

## 🗄️ 数据库操作

### PostgreSQL

```bash
# 连接数据库
psql -h localhost -U claude_memory -d claude_memory_db

# 常用查询
\dt                          # 列出所有表
SELECT COUNT(*) FROM messages;  # 消息总数
SELECT COUNT(*) FROM conversations;  # 对话总数

# 备份和恢复
pg_dump -h localhost -U claude_memory claude_memory_db > backup.sql
psql -h localhost -U claude_memory claude_memory_db < backup.sql
```

### Qdrant

```bash
# 查看集合
curl http://localhost:6333/collections

# 查看特定集合信息
curl http://localhost:6333/collections/claude_memory_vectors_v14

# 计算向量数量
curl -X POST http://localhost:6333/collections/claude_memory_vectors_v14/points/count \
  -H "Content-Type: application/json" -d '{}'
```

## 🛠️ 维护命令

### 日常维护

```bash
# 生成成本容量报告
python3 scripts/cost_capacity_monitor.py

# 数据库维护
python3 scripts/db_maintenance.py

# 系统备份
./scripts/backup_system.sh

# 清理旧日志
find logs/ -name "*.log" -mtime +30 -delete
```

### 配置更新

```bash
# 重新加载Prometheus配置
sudo systemctl reload prometheus

# 重新加载Alertmanager配置  
sudo systemctl reload alertmanager

# 更新MCP配置
python3 scripts/update_mcp_to_monitoring.py
```

## 🚨 故障处理

### 常见问题快速修复

```bash
# MCP服务器启动失败
sudo systemctl restart claude-memory-mcp-monitoring
tail -f logs/monitoring_mcp.log

# PostgreSQL连接问题
sudo systemctl restart postgresql
sudo -u postgres psql -c "ALTER USER claude_memory PASSWORD 'password';"

# Qdrant服务异常
sudo systemctl restart qdrant
curl http://localhost:6333/cluster

# 磁盘空间不足
sudo du -sh /* | sort -hr | head -10
sudo find /tmp -type f -atime +7 -delete

# 内存不足
sudo systemctl restart postgresql qdrant
free -h && sync && echo 3 > /proc/sys/vm/drop_caches
```

### 应急联系

| 严重级别 | 响应时间 | 处理方式 |
|----------|----------|----------|
| P0 - 紧急 | < 15分钟 | 立即响应，服务完全不可用 |
| P1 - 高 | < 1小时 | 性能严重下降 |
| P2 - 中 | < 4小时 | 部分功能异常 |
| P3 - 低 | < 24小时 | 优化改进 |

## 📊 报告生成

### 自动报告

| 报告类型 | 频率 | 脚本 | 位置 |
|----------|------|------|------|
| 成本容量 | 每小时 | `cost_capacity_monitor.py` | `reports/` |
| 周度分析 | 每周一 | `weekly_analysis.py` | `reports/` |
| 维护报告 | 每月 | `db_maintenance.py` | `reports/` |

### 手动报告

```bash
# 生成即时成本报告
python3 scripts/cost_capacity_monitor.py

# 生成周度分析
python3 scripts/weekly_analysis.py

# 验证部署状态
python3 scripts/deployment_verification.py
```

## 🔐 重要凭据

| 服务 | 用户名 | 密码 | 说明 |
|------|--------|------|------|
| PostgreSQL | claude_memory | password | 主数据库 |
| System User | jetgogoing | - | 系统用户 |

## 📞 重要命令速记

```bash
# 一键部署
./scripts/deploy_monitoring.sh

# 一键验证
python3 scripts/deployment_verification.py

# 一键备份
./scripts/backup_system.sh

# 一键报告
python3 scripts/cost_capacity_monitor.py

# 查看所有服务
./scripts/monitoring_control.sh status

# 查看所有日志
tail -f logs/*.log
```

---

**版本**: 1.4.0-monitoring  
**最后更新**: 2025-07-07  
**打印友好**: 建议A4纸张，双面打印