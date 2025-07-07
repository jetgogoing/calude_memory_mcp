# Claude Memory 管理脚本索引

> **用途**: 列出所有管理脚本及其使用方法  
> **更新时间**: 2025-07-07

## 📁 脚本目录结构

```
scripts/
├── 部署和配置
│   ├── deploy_monitoring.sh          # 部署监控系统
│   ├── update_mcp_to_monitoring.py   # 更新MCP配置
│   ├── setup_monitoring_cron.sh      # 设置监控cron任务
│   └── configure_claude_cli.py       # 配置Claude CLI
├── 监控和报告
│   ├── cost_capacity_monitor.py      # 成本容量监控
│   ├── weekly_analysis.py            # 周度分析报告
│   ├── monitoring.py                 # 系统监控检查
│   └── alert_webhook.py              # 告警webhook处理
├── 数据库管理
│   ├── init_database.py              # 初始化数据库
│   ├── db_maintenance.py             # 数据库维护
│   └── backup_system.sh              # 数据备份
├── 测试和验证
│   ├── test_mcp_integration.py       # MCP集成测试
│   ├── deployment_verification.py    # 部署验证
│   └── force_mcp_test.py             # 强制MCP测试
└── 工具脚本
    ├── monitoring_control.sh          # 监控服务控制
    ├── start_mcp_service.py           # 启动MCP服务
    └── restart_claude_cli.py          # 重启Claude CLI
```

## 🚀 部署和配置脚本

### deploy_monitoring.sh
**用途**: 一键部署完整监控系统  
**依赖**: 需要sudo权限  
**使用方法**:
```bash
chmod +x scripts/deploy_monitoring.sh
./scripts/deploy_monitoring.sh
```
**功能**:
- 下载并安装Prometheus、Alertmanager
- 配置systemd服务
- 验证配置文件
- 启动所有监控服务

### update_mcp_to_monitoring.py
**用途**: 更新Claude CLI配置使用监控版MCP服务器  
**使用方法**:
```bash
python3 scripts/update_mcp_to_monitoring.py
```
**功能**:
- 更新`~/.claude.json`配置
- 创建备份文件
- 生成systemd服务配置

### setup_monitoring_cron.sh
**用途**: 设置自动监控任务  
**使用方法**:
```bash
chmod +x scripts/setup_monitoring_cron.sh
./scripts/setup_monitoring_cron.sh
```
**功能**:
- 配置cron定时任务
- 设置日志目录
- 显示当前计划任务

### configure_claude_cli.py
**用途**: 配置Claude CLI MCP设置  
**使用方法**:
```bash
python3 scripts/configure_claude_cli.py
```

## 📊 监控和报告脚本

### cost_capacity_monitor.py
**用途**: 生成成本与容量监控报告  
**使用方法**:
```bash
python3 scripts/cost_capacity_monitor.py
```
**输出文件**:
- `reports/cost_capacity_report_*.json` - JSON格式详细报告
- `reports/cost_capacity_summary_*.md` - 可读摘要报告
- `reports/dashboard_data.json` - 仪表板数据

**功能**:
- 分析30天成本数据
- 检查系统容量状态
- 生成告警和建议
- 创建仪表板数据

### weekly_analysis.py
**用途**: 生成周度深度分析报告  
**使用方法**:
```bash
python3 scripts/weekly_analysis.py
```
**输出文件**:
- `reports/weekly_analysis_*.json` - 详细分析数据
- `reports/weekly_analysis_*.md` - 可读分析报告

**功能**:
- 7天使用趋势分析
- 模型使用统计
- 成本效率评估
- 优化建议生成

### monitoring.py
**用途**: 系统监控检查  
**使用方法**:
```bash
python3 scripts/monitoring.py
```
**功能**:
- 检查所有服务状态
- 验证数据库连接
- 输出JSON监控数据

### alert_webhook.py
**用途**: 告警webhook处理服务  
**使用方法**:
```bash
python3 scripts/alert_webhook.py
```
**功能**:
- 接收Alertmanager告警
- 记录告警到日志文件
- 分级处理不同严重程度告警

## 🗄️ 数据库管理脚本

### init_database.py
**用途**: 初始化PostgreSQL数据库和表结构  
**使用方法**:
```bash
python3 scripts/init_database.py
```
**功能**:
- 创建数据库表
- 设置索引和约束
- 验证表结构

### db_maintenance.py
**用途**: 数据库维护操作  
**使用方法**:
```bash
# 完整维护
python3 scripts/db_maintenance.py

# 仅清理数据
python3 scripts/db_maintenance.py --cleanup-only

# 自定义保留天数
python3 scripts/db_maintenance.py --days 60
```
**功能**:
- 清理旧数据 (默认90天)
- 数据库优化 (VACUUM, ANALYZE)
- 自动备份
- 健康状态检查
- 生成维护报告

### backup_system.sh
**用途**: 系统数据备份  
**使用方法**:
```bash
./scripts/backup_system.sh
```
**功能**:
- PostgreSQL数据库备份
- SQLite数据库备份
- 配置文件备份
- 自动压缩和清理

## 🧪 测试和验证脚本

### test_mcp_integration.py
**用途**: MCP集成测试  
**使用方法**:
```bash
python3 scripts/test_mcp_integration.py
```
**功能**:
- 测试MCP服务器连接
- 验证所有工具函数
- 检查JSON-RPC协议

### deployment_verification.py
**用途**: 部署后验证  
**使用方法**:
```bash
python3 scripts/deployment_verification.py
```
**功能**:
- 8步完整验证流程
- 检查所有服务状态
- 验证配置正确性
- 生成验证报告

### force_mcp_test.py
**用途**: 强制MCP功能测试  
**使用方法**:
```bash
python3 scripts/force_mcp_test.py
```

## 🛠️ 工具脚本

### monitoring_control.sh
**用途**: 监控服务控制  
**使用方法**:
```bash
# 启动监控服务
./scripts/monitoring_control.sh start

# 停止监控服务
./scripts/monitoring_control.sh stop

# 重启监控服务
./scripts/monitoring_control.sh restart

# 查看服务状态
./scripts/monitoring_control.sh status

# 查看服务日志
./scripts/monitoring_control.sh logs
```

### start_mcp_service.py
**用途**: 启动MCP服务  
**使用方法**:
```bash
python3 scripts/start_mcp_service.py
```

### restart_claude_cli.py
**用途**: 重启Claude CLI进程  
**使用方法**:
```bash
python3 scripts/restart_claude_cli.py
```

## 📅 定时任务脚本

通过`setup_monitoring_cron.sh`设置的自动任务：

| 时间 | 脚本 | 功能 |
|------|------|------|
| 每小时 | `cost_capacity_monitor.py` | 容量状态检查 |
| 每日8点 | `cost_capacity_monitor.py` | 成本报告生成 |
| 每周一9点 | `weekly_analysis.py` | 周度分析报告 |
| 每月1号2点 | `db_maintenance.py` | 数据库维护 |
| 每5分钟 | 仪表板数据更新 | 更新监控数据 |
| 每日3点 | `backup_system.sh` | 系统备份 |

## 🔍 脚本依赖关系

```
部署流程:
deploy_monitoring.sh → update_mcp_to_monitoring.py → setup_monitoring_cron.sh

监控流程:
cost_capacity_monitor.py → weekly_analysis.py → db_maintenance.py

测试流程:
init_database.py → deployment_verification.py → test_mcp_integration.py
```

## 📋 快速参考

### 常用命令组合

```bash
# 完整部署
./scripts/deploy_monitoring.sh && python3 scripts/update_mcp_to_monitoring.py

# 完整验证
python3 scripts/deployment_verification.py && python3 scripts/test_mcp_integration.py

# 监控检查
./scripts/monitoring_control.sh status && python3 scripts/monitoring.py

# 数据维护
python3 scripts/db_maintenance.py && ./scripts/backup_system.sh
```

### 故障排除脚本

| 问题类型 | 推荐脚本 |
|----------|----------|
| 服务启动失败 | `monitoring_control.sh status` |
| 数据库问题 | `init_database.py`, `db_maintenance.py` |
| MCP连接问题 | `test_mcp_integration.py` |
| 性能问题 | `cost_capacity_monitor.py` |
| 配置问题 | `deployment_verification.py` |

---

**文档版本**: 1.4.0  
**维护者**: Claude Memory团队  
**最后更新**: 2025-07-07