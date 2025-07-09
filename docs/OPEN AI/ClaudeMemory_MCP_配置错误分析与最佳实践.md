# 📘 Claude Memory MCP 配置错误分析与最佳实践指南

**目标**：部署一个可移植、可共享、零配置的 Claude Memory MCP 服务，避免路径硬编码问题与命名不匹配问题。

---

## ❗ 问题一：路径硬编码导致配置不可移植

### 🚫 错误示例

```json
{
  "mcpServers": {
    "claude-memory": {
      "command": "/home/jetgogoing/claude_memory/venv/bin/python",
      "args": ["-m", "claude_memory.mcp_server"],
      "cwd": "/home/jetgogoing/claude_memory",
      "env": {
        "PYTHONPATH": "/home/jetgogoing/claude_memory/src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### ❌ 问题说明

- 路径中包含了具体用户目录 `/home/jetgogoing`，无法被其他人复用
- 更换电脑或系统结构就无法使用

### ✅ 正确示例（推荐）

使用项目内部脚本 `mcp/start.sh` 启动，并使用相对路径：

```json
{
  "mcpServers": {
    "claude-memory": {
      "command": "./mcp/start.sh",
      "cwd": ".",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  },
  "defaultMcp": "claude-memory"
}
```

---

## ❗ 问题二：`.mcp.json` 服务名与配置中注册的不一致

### 🚫 场景描述

`.mcp.json` 中写了：

```json
{ "mcp": "claude-memory" }
```

但全局配置文件中注册的是：

```json
"mcpServers": {
  "claude-memory-mcp": { ... }
}
```

### ❌ 结果

Claude CLI 启动后无法匹配到 `"claude-memory"`，于是忽略你的 MCP 服务，回退到默认服务（如 `zen`）。

### ✅ 正确做法

统一 `.mcp.json` 和配置中 MCP 名称，例如都用 `claude-memory`：

#### `.mcp.json`

```json
{ "mcp": "claude-memory" }
```

#### 配置文件 `~/.config/claude/claude_desktop_config.json`

```json
"mcpServers": {
  "claude-memory": {
    "command": "./mcp/start.sh",
    "cwd": ".",
    "env": {
      "PYTHONUNBUFFERED": "1"
    }
  }
}
```

---

## ✅ 最佳实践总结

| 项目 | 建议 |
|------|------|
| 启动脚本 | 放在项目目录 `mcp/start.sh` 中，使用相对路径 |
| MCP 名称 | 在 `.mcp.json` 与全局配置中保持一致 |
| 路径配置 | 使用相对路径，避免写死用户名 |
| CLI 配置 | 可设置 `defaultMcp`，实现全局默认服务 |
| 共享协作 | 所有配置应放在项目内，便于 clone 后即用 |

---

## 🧪 测试验证

1. 设置 `.mcp.json`
2. 启动 `claude` CLI
3. 执行 `/status` 或 `claude mcp claude-memory health_check` 查看连接状态

---

**作者**：Claude Code  
**时间**：自动生成于 2025-07-09
