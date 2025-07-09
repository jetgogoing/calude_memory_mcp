# Claude Memory 全自动链路启动方案

**目标**：确保只要打开 VS Code 或新终端，系统就会自动运行以下所有组件，无需手动启动：

- ✅ PostgreSQL
- ✅ Qdrant
- ✅ Claude MCP（JSON-RPC 协议服务）
- ✅ Claude API Server（RESTful 接口）

---

## 🧠 一、当前现状分析

| 模块         | 启动方式         | 当前是否自动启动 |
|--------------|------------------|------------------|
| PostgreSQL   | Docker Compose   | ✅ 是             |
| Qdrant       | Docker Compose   | ✅ 是             |
| MCP Server   | `start_mcp_direct.py` | ✅ 是        |
| API Server   | `start_api_server.py` 或类似脚本 | ❌ 否 |

目前 `auto_start_memory_system.sh` 仅启动了前三者，但 **API Server 尚未加入自动链路**，导致你必须手动执行 `./start_api_background.sh` 或其他脚本。

---

## 🚀 二、解决方案：构建统一启动控制器

### ✨ 方案核心：创建 `start_all_services.sh`

此脚本将统一启动所有依赖服务，包含数据库、MCP、API 服务。

```bash
#!/bin/bash
set -e

echo "🚀 启动 PostgreSQL 与 Qdrant（Docker）..."
docker compose -f docker/docker-compose.yml up -d postgres qdrant

echo "🚀 启动 Claude MCP Server..."
source venv/bin/activate
nohup python start_mcp_direct.py > logs/mcp.log 2>&1 &

echo "🚀 启动 Claude API Server..."
nohup python start_api_server.py > logs/api.log 2>&1 &

echo "✅ 所有服务启动完毕。"
```

> 说明：
> - 使用 `nohup` 保证后台运行，不依赖当前终端
> - 日志分别输出到 `logs/` 目录，便于调试
> - `start_api_server.py` 需替换为你项目中实际的 API 启动文件名

---

## ⚙️ 三、修改 auto_start_memory_system.sh（调用新控制器）

修改 `auto_start_memory_system.sh`，使其只调用新控制器：

```bash
#!/bin/bash
[ -x "$HOME/claude_memory/start_all_services.sh" ] && "$HOME/claude_memory/start_all_services.sh"
```

---

## 🧩 四、确保 VS Code 或新终端自动触发

你可以在以下位置添加自动执行逻辑：

### 方法 A：添加到 `~/.bashrc` 或 `~/.zshrc`

```bash
# 自动执行 Claude Memory 启动
[ -x "$HOME/claude_memory/auto_start_memory_system.sh" ] && "$HOME/claude_memory/auto_start_memory_system.sh" &
```

### 方法 B：VS Code 设置启动 profile

在 `.vscode/settings.json` 中添加：

```json
"terminal.integrated.profiles.linux": {
  "AutoMemory": {
    "path": "/bin/bash",
    "args": ["-c", "$HOME/claude_memory/auto_start_memory_system.sh"]
  }
},
"terminal.integrated.defaultProfile.linux": "AutoMemory"
```

---

## ✅ 五、验证启动是否成功

### 验证命令：

```bash
docker ps  # 检查 Postgres / Qdrant 是否 healthy
ps aux | grep mcp_direct.py
ps aux | grep api_server.py
lsof -i:8000  # 查看 API 是否监听
```

### 健康检查脚本（可选）：

```bash
curl http://localhost:8000/health
```

预期输出：

```json
{"status":"ok"}
```

---

## 📦 六、附加建议

1. 将 `logs/` 添加到 `.gitignore`
2. 如有 pm2 / systemd / supervisord，可将 `start_all_services.sh` 设为守护任务
3. 可将 `start_api_server.py` 支持 `--port` 参数，便于环境部署

---

## ✅ 最终效果：VS Code 一开，全系统即起

- 不再需要手动点击任何脚本
- 全链路服务自启动，日志可查，状态可监控
- 整体部署行为更像一个专业级系统

> **至此，你的 Claude Memory 项目将实现真正的一键全自动启动。**
