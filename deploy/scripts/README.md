# 部署脚本说明

本目录包含 Claude Memory MCP Service 的所有运维脚本。

## 基础操作脚本

### start.sh - 启动服务
```bash
./deploy/scripts/start.sh
```
- 检查 Docker 环境
- 自动创建配置文件
- 启动所有服务
- 执行健康检查

### stop.sh - 停止服务
```bash
./deploy/scripts/stop.sh
```
- 优雅停止所有服务
- 保留数据卷

### logs.sh - 查看日志
```bash
./deploy/scripts/logs.sh [service]
```
- 查看所有服务日志：`./logs.sh`
- 查看特定服务：`./logs.sh postgres`

### health-check.sh - 健康检查
```bash
./deploy/scripts/health-check.sh
```
- 检查所有服务状态
- 验证连接性
- 显示资源使用情况

### clean.sh - 清理数据
```bash
./deploy/scripts/clean.sh
```
- ⚠️ **危险操作**：删除所有数据
- 需要手动确认
- 用于完全重置环境

## 数据管理脚本

### backup.sh - 数据备份
```bash
# 默认备份
./deploy/scripts/backup.sh

# 指定备份目录
./deploy/scripts/backup.sh -d /path/to/backups

# 自定义备份名称
./deploy/scripts/backup.sh -n my_backup_20240115
```

备份内容：
- PostgreSQL 数据库完整备份
- Qdrant 向量数据库快照
- 配置文件（排除敏感信息）

备份文件格式：`claude_memory_backup_YYYYMMDD_HHMMSS.tar.gz`

### restore.sh - 数据恢复
```bash
# 从备份文件恢复
./deploy/scripts/restore.sh backups/claude_memory_backup_20240115_120000.tar.gz
```

恢复流程：
1. 验证备份文件完整性
2. 显示备份信息
3. 确认恢复操作
4. 恢复 PostgreSQL 数据
5. 恢复 Qdrant 向量数据
6. 显示配置差异

## 高级脚本

### docker-start.sh - Docker 特定启动
用于特殊 Docker 环境配置

### start_production_local.sh - 本地生产环境
模拟生产环境的本地部署

### deploy_production_ubuntu.sh - Ubuntu 生产部署
用于 Ubuntu 服务器的自动化部署

## 使用建议

### 日常运维流程

1. **启动服务**
   ```bash
   ./start.sh  # 从项目根目录
   ```

2. **监控服务**
   ```bash
   ./deploy/scripts/logs.sh -f  # 实时日志
   ./deploy/scripts/health-check.sh  # 健康状态
   ```

3. **定期备份**
   ```bash
   # 建议通过 cron 定期执行
   0 2 * * * /path/to/deploy/scripts/backup.sh
   ```

4. **停止服务**
   ```bash
   ./stop.sh  # 从项目根目录
   ```

### 故障恢复流程

1. **服务异常**
   ```bash
   ./deploy/scripts/health-check.sh  # 诊断问题
   ./deploy/scripts/logs.sh | tail -100  # 查看最近日志
   ```

2. **数据恢复**
   ```bash
   # 列出可用备份
   ls -la backups/
   
   # 恢复到特定备份
   ./deploy/scripts/restore.sh backups/claude_memory_backup_XXXXX.tar.gz
   ```

3. **完全重置**
   ```bash
   ./deploy/scripts/clean.sh  # 清理所有数据
   ./deploy/scripts/start.sh  # 重新启动
   ```

## 环境变量

脚本支持的环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BACKUP_DIR` | 备份目录 | `./backups` |
| `COMPOSE_CMD` | Docker Compose 命令 | 自动检测 |
| `DOCKER_DIR` | Docker 配置目录 | `deploy/docker` |

## 注意事项

1. **权限要求**：所有脚本需要执行权限
   ```bash
   chmod +x deploy/scripts/*.sh
   ```

2. **Docker 依赖**：确保 Docker 和 Docker Compose 已安装

3. **端口冲突**：默认使用端口 5432（PostgreSQL）和 6333（Qdrant）

4. **数据安全**：
   - 定期备份重要数据
   - 测试恢复流程
   - 保护备份文件