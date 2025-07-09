# 全局共享记忆中心部署方案

## ✅ 背景与目标

当前 Claude Memory MCP 系统存在以下问题：

- MCP 服务注册为会话级别，无法跨项目访问
- 对话无法自动写入数据库，需手动工具调用
- 每个项目的 project_id 不一致，隔离严重

**目标：** 将 Memory MCP 架构升级为全局共享服务中心，实现跨项目、多会话记忆共享。

---

## 🧠 新架构概览

```
Ubuntu 主机
│
├── Claude Code CLI
│     ├── ~/.claude.json （全局注册MCP）
│     └── 会话 ↔ MCP（stdio 工具调用）
│
├── Claude Memory MCP 服务目录
│     ├── mcp_server.py （stdio模式工具响应）
│     ├── api_server.py （长期驻守HTTP接口）
│     ├── collector.py   （自动监听Claude CLI日志）
│     └── .env
│
├── PostgreSQL（聊天日志）
└── Qdrant（嵌入向量）
```

---

## 🔌 `.claude.json` 配置示例（全局注册）

```json
{
  "mcpServers": {
    "claude-memory": {
      "type": "stdio",
      "command": "/home/jetgogoing/claude_memory/mcp/start.sh",
      "cwd": "/home/jetgogoing/claude_memory",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

> ✅ 使用 `stdio` 保证 MCP 在所有 CLI 项目中都可调用。

---

## 🌍 project_id 策略统一

- 所有会话存储的记忆使用统一的 `project_id = "global"`
- 所有查询检索也统一基于该 ID
- 支持未来自动切换：可从 CLI 当前工作目录计算 hash 作为逻辑 ID

---

## 🔄 自动收集模块：ConversationCollector

监听 Claude CLI 的 JSONL 日志文件，如：

```bash
tail -f ~/.claude/conversations/2025-07-09.jsonl | python collector.py
```

处理逻辑：

- 解析 message_type = user/assistant
- 拼接成完整对话结构
- 存入数据库，并进行嵌入向量生成

---

## 🌐 后台 API 服务（用于 CLI 工具调用）

- 使用 FastAPI 提供 REST 接口
- 所有工具方法（如 memory_add、memory_search）转为 HTTP 请求
- 可部署为 systemd / docker 持久进程

---

## 🐳 Docker-Compose 示例

```yaml
version: '3.9'
services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: claude_memory
      POSTGRES_USER: claude_memory
      POSTGRES_PASSWORD: password
    volumes:
      - ./postgres:/var/lib/postgresql/data
    ports:
      - "5433:5432"

  qdrant:
    image: qdrant/qdrant
    volumes:
      - ./qdrant:/qdrant/storage
    ports:
      - "6333:6333"

  claude-memory-api:
    build: .
    command: ["python", "api_server.py"]
    environment:
      - DATABASE_URL=postgresql://claude_memory:password@postgres:5432/claude_memory
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - postgres
      - qdrant
```

---

## 🧪 验收清单

| 验证项                        | 说明                             |
|-----------------------------|----------------------------------|
| ✅ CLI 打开是否自动连接 MCP  | `claude-memory` 工具是否可用     |
| ✅ API 是否可独立访问        | `curl http://localhost:8000/health` |
| ✅ 自动收集是否生效          | 新对话是否自动进入数据库与 Qdrant |
| ✅ 跨项目查询是否成功        | 不同目录下是否都能检索记忆       |

---

## 🧾 环境变量模板 `.env`

```
DATABASE_URL=postgresql://claude_memory:password@localhost:5433/claude_memory
QDRANT_URL=http://localhost:6333
PROJECT_ID=global
GEMINI_API_KEY=xxx
SILICONFLOW_API_KEY=xxx
```

---

系统准备完成后，即可投入正式开发与共享记忆使用。