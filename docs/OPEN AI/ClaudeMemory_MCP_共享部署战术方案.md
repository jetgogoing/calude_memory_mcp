# 🧠 Claude Memory MCP 服务共享部署战术执行方案

## 🎯 目标理解

我们希望部署一个 Claude Memory MCP Server，使其具备以下特点：

1. ✅ 像 ZEN 一样是“预配置好”的服务，可在任何项目中自动使用
2. ✅ 无需在配置文件中硬编码绝对路径
3. ✅ 支持多人协作或开源共享，clone 后无需修改配置即可使用
4. ✅ 启动方式可被 Claude CLI 自动识别和加载（通过 `.mcp.json`）

---

## 📁 项目结构设计

```
shared-memory-project/
├── .mcp.json              ← 绑定 MCP 名称（项目内部使用）
├── .claude.json           ← 设置项目 ID（可选）
├── mcp/
│   ├── start.sh           ← MCP 启动脚本（相对路径）
│   └── requirements.txt   ← MCP 所需依赖
├── src/                   ← Claude Memory 服务代码目录（src/claude_memory/...）
├── venv/                  ← Python 虚拟环境（本地创建）
├── README.md
```

---

## ⚙️ 配置说明

### `.mcp.json`

```json
{
  "mcp": "shared-memory"
}
```

### `.claude.json`

```json
{
  "projectId": "shared-memory-project"
}
```

### Claude CLI 全局配置（~/.config/claude/claude_desktop_config.json）

添加以下内容：

```json
{
  "mcpServers": {
    "shared-memory": {
      "command": "./mcp/start.sh",
      "cwd": ".",
      "env": {
        "PYTHONPATH": "./src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

:::info
注意：不要使用绝对路径，所有路径应为相对项目目录的相对路径。
:::

---

## 🛠 `mcp/start.sh` 启动脚本示例

```bash
#!/bin/bash
# 启动 Claude Memory MCP Server（stdio 模式）

# 定位项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 激活虚拟环境
source venv/bin/activate

# 启动 MCP 服务
exec python -m claude_memory.mcp_server
```

> Windows 用户可添加 `start.ps1`

---

## ✅ 使用流程

1. 克隆项目：
   ```bash
   git clone https://your.repo/shared-memory-project.git
   cd shared-memory-project
   ```

2. 创建虚拟环境并安装依赖：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r mcp/requirements.txt
   ```

3. 启动 Claude CLI：
   ```bash
   claude
   ```

   CLI 会自动识别 `.mcp.json` 并加载 `shared-memory` 服务。

---

## 🧪 测试命令

```bash
claude mcp shared-memory search_memories --query "测试"
```

---

## 🧠 总结

| 特性 | 说明 |
|------|------|
| 可移植性 | 所有路径均为相对路径 |
| 易用性 | 无需修改配置，自动识别 |
| 支持协作 | 团队成员或其他开发者 clone 后可立即使用 |
| 类似 ZEN | 无需额外绑定，默认出现在 Claude CLI 中 |
