# Claude Memory MCP服务 运维手册 (Runbook)

> **版本**: 1.4.0-monitoring  
> **更新时间**: 2025-07-07  
> **负责人**: Claude Memory团队  

## 📋 目录

- [系统概述](#系统概述)
- [服务架构](#服务架构)
- [部署指南](#部署指南)
- [日常运维](#日常运维)
- [监控告警](#监控告警)
- [故障排除](#故障排除)
- [维护操作](#维护操作)
- [应急响应](#应急响应)
- [联系信息](#联系信息)

## 🏗️ 系统概述

Claude Memory MCP服务是一个智能记忆管理系统，为Claude CLI提供持久化对话记忆和语义检索功能。

### 核心组件
- **MCP服务器**: 主要业务逻辑，提供记忆搜索、健康检查等功能
- **PostgreSQL**: 主数据库，存储对话记录和元数据
- **Qdrant**: 向量数据库，提供语义搜索能力
- **Prometheus**: 监控数据收集
- **Alertmanager**: 告警管理和通知
- **Webhook服务**: 告警处理和通知

### 技术栈
- Python 3.10+
- PostgreSQL 14+
- Qdrant 1.7+
- Prometheus 2.45+
- Alertmanager 0.25+

## 🏛️ 服务架构

```
Claude CLI
    ↓ JSON-RPC 2.0
MCP服务器 (监控版)
    ↓
┌─PostgreSQL (对话数据)
├─Qdrant (向量检索)
├─Prometheus (指标收集)
├─Alertmanager (告警管理)
└─Webhook (告警处理)
```

### 端口分配
- **8080**: MCP服务器指标端点
- **5432**: PostgreSQL
- **6333**: Qdrant
- **9090**: Prometheus
- **9093**: Alertmanager
- **8081**: 告警Webhook

## 🚀 部署指南

### 1. 环境准备

```bash
# 克隆项目
git clone <repository>
cd claude_memory

# 创建Python虚拟环境
python3 -m venv venv-claude-memory
source venv-claude-memory/bin/activate
pip install -r requirements.txt
```

### 2. 数据库配置

```bash
# 初始化PostgreSQL
sudo -u postgres createuser claude_memory
sudo -u postgres createdb claude_memory_db -O claude_memory
sudo -u postgres psql -c "ALTER USER claude_memory PASSWORD 'password';"

# 初始化数据库表
python3 scripts/init_database.py
```

### 3. 服务部署

```bash
# 部署监控系统
./scripts/deploy_monitoring.sh

# 配置Claude CLI
python3 scripts/update_mcp_to_monitoring.py

# 设置自动监控任务
./scripts/setup_monitoring_cron.sh
```

### 4. 验证部署

```bash
# 检查服务状态
sudo systemctl status prometheus alertmanager claude-memory-webhook

# 测试MCP服务
python3 scripts/test_mcp_integration.py
```

## 📊 日常运维

### 每日检查清单

- [ ] 检查所有服务状态
- [ ] 查看监控告警
- [ ] 检查系统资源使用
- [ ] 验证备份完成
- [ ] 查看错误日志

### 检查命令

```bash
# 服务状态检查
sudo systemctl status prometheus alertmanager claude-memory-webhook
./scripts/monitoring_control.sh status

# 健康检查
curl http://localhost:8080/health
curl http://localhost:9090/-/healthy
curl http://localhost:9093/-/healthy

# 资源监控
df -h  # 磁盘空间
free -h  # 内存使用
top  # CPU使用

# 日志查看
tail -f logs/monitoring_mcp.log
tail -f logs/alerts.log
sudo journalctl -u prometheus -f
```

### 性能指标

| 指标 | 正常范围 | 警告阈值 | 紧急阈值 |
|------|----------|----------|----------|
| 磁盘使用率 | < 70% | 80% | 90% |
| 内存使用率 | < 80% | 85% | 95% |
| CPU使用率 | < 70% | 80% | 90% |
| 响应时间 | < 2s | 5s | 10s |
| 数据库大小 | < 500MB | 1GB | 2GB |

## 🚨 监控告警

### Prometheus指标

访问 http://localhost:9090 查看所有指标：

- `claude_memory_uptime_seconds`: 服务运行时间
- `claude_memory_requests_total`: 总请求数
- `claude_memory_postgres_up`: PostgreSQL状态
- `claude_memory_qdrant_up`: Qdrant状态
- `claude_memory_avg_response_time_seconds`: 平均响应时间

### 告警规则

| 告警名称 | 触发条件 | 严重级别 | 响应时间 |
|----------|----------|----------|----------|
| ClaudeMemoryMCPDown | 服务离线30秒 | Critical | 立即 |
| ClaudeMemoryPostgresDown | PostgreSQL离线1分钟 | Critical | 立即 |
| ClaudeMemoryQdrantDown | Qdrant离线1分钟 | Critical | 立即 |
| ClaudeMemoryHighResponseTime | 响应时间>5秒持续2分钟 | Warning | 15分钟 |

### 告警处理

告警通过Webhook发送到 http://localhost:8081，自动记录到：
- **日志文件**: `logs/alerts.log`
- **Alertmanager界面**: http://localhost:9093

## 🔧 故障排除

### 常见问题

#### 1. MCP服务器启动失败

**症状**: Claude CLI显示MCP服务器failed状态

**诊断**:
```bash
# 检查日志
tail -f logs/monitoring_mcp.log

# 手动启动测试
python3 monitoring_mcp_server.py
```

**解决方案**:
- 检查PostgreSQL连接
- 验证Python依赖
- 查看端口冲突

#### 2. PostgreSQL连接失败

**症状**: 数据库连接错误

**诊断**:
```bash
# 检查PostgreSQL状态
sudo systemctl status postgresql

# 测试连接
psql -h localhost -U claude_memory -d claude_memory_db
```

**解决方案**:
- 重启PostgreSQL服务
- 检查认证配置 (`pg_hba.conf`)
- 验证用户权限

#### 3. Qdrant服务异常

**症状**: 向量搜索失败

**诊断**:
```bash
# 检查Qdrant状态
curl http://localhost:6333/cluster

# 查看集合状态
curl http://localhost:6333/collections
```

**解决方案**:
- 重启Qdrant服务
- 检查数据目录权限
- 重建向量集合

#### 4. 监控告警不工作

**症状**: 无法收到告警通知

**诊断**:
```bash
# 检查Alertmanager状态
curl http://localhost:9093/-/healthy

# 查看告警规则
curl http://localhost:9090/api/v1/rules

# 测试Webhook
curl -X POST http://localhost:8081/webhook -d '{"alerts":[{"status":"firing"}]}'
```

**解决方案**:
- 重启Alertmanager服务
- 检查告警规则配置
- 验证Webhook服务

### 日志文件位置

| 组件 | 日志位置 |
|------|----------|
| MCP服务器 | `logs/monitoring_mcp.log` |
| 告警Webhook | `logs/alerts.log` |
| Prometheus | `sudo journalctl -u prometheus` |
| Alertmanager | `sudo journalctl -u alertmanager` |
| PostgreSQL | `/var/log/postgresql/` |
| Cron任务 | `logs/cron.log` |

## 🛠️ 维护操作

### 数据库维护

```bash
# 月度维护 (自动执行)
python3 scripts/db_maintenance.py

# 手动备份
./scripts/backup_system.sh

# 数据清理
python3 scripts/db_maintenance.py --cleanup-days 60
```

### 配置更新

```bash
# 重新加载Prometheus配置
sudo systemctl reload prometheus

# 重新加载Alertmanager配置
sudo systemctl reload alertmanager

# 更新MCP服务器
sudo systemctl restart claude-memory-mcp-monitoring
```

### 扩容操作

#### 磁盘扩容
1. 扩展物理磁盘
2. 调整文件系统大小
3. 更新监控阈值

#### 内存扩容
1. 增加物理内存
2. 调整PostgreSQL配置
3. 重启相关服务

### 数据迁移

```bash
# 导出数据
pg_dump -h localhost -U claude_memory claude_memory_db > backup.sql

# 导入数据
psql -h new_host -U claude_memory claude_memory_db < backup.sql

# 向量数据迁移
# (使用Qdrant快照功能)
```

## 🚑 应急响应

### 严重级别定义

#### P0 - 紧急 (< 15分钟响应)
- 服务完全不可用
- 数据丢失风险
- 安全漏洞

#### P1 - 高优先级 (< 1小时响应)
- 性能严重下降
- 部分功能不可用
- 重要告警持续触发

#### P2 - 中优先级 (< 4小时响应)
- 性能轻微下降
- 非关键功能异常
- 一般性告警

#### P3 - 低优先级 (< 24小时响应)
- 优化改进
- 文档更新
- 非紧急维护

### 应急联系人

| 角色 | 姓名 | 电话 | 邮箱 | 主要职责 |
|------|------|------|------|----------|
| 系统管理员 | Claude Admin | - | admin@claude.ai | 系统运维 |
| 开发负责人 | Dev Lead | - | dev@claude.ai | 代码问题 |
| 数据库管理员 | DBA | - | dba@claude.ai | 数据库问题 |

### 应急操作手册

#### 服务完全不可用

1. **立即行动** (0-5分钟)
   ```bash
   # 检查基础服务
   sudo systemctl status postgresql qdrant
   
   # 重启核心服务
   sudo systemctl restart claude-memory-mcp-monitoring
   
   # 检查磁盘空间
   df -h
   ```

2. **诊断分析** (5-15分钟)
   ```bash
   # 查看详细日志
   tail -f logs/monitoring_mcp.log
   sudo journalctl -u prometheus -n 50
   
   # 检查网络连接
   netstat -tulpn | grep -E '(5432|6333|8080)'
   ```

3. **问题修复** (15-30分钟)
   - 根据日志确定根本原因
   - 执行相应修复操作
   - 验证服务恢复

4. **后续跟进**
   - 更新监控告警
   - 编写事故报告
   - 改进预防措施

## 📞 联系信息

### 技术支持
- **文档**: 项目根目录 `docs/`
- **问题追踪**: GitHub Issues
- **紧急联系**: 系统管理员

### 有用链接
- **Prometheus界面**: http://localhost:9090
- **Alertmanager界面**: http://localhost:9093
- **监控指标**: http://localhost:8080/metrics
- **健康检查**: http://localhost:8080/health

---

**文档版本**: 1.4.0  
**最后更新**: 2025-07-07  
**下次审查**: 2025-08-07