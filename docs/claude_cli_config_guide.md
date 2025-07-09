# Claude CLI 全局配置指南

## 配置 Claude Memory MCP 服务

要在 Claude CLI 中全局使用 Claude Memory 服务，请按照以下步骤配置：

### 1. 找到 Claude CLI 配置文件

配置文件位置：
- **Linux/macOS**: `~/.config/claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\claude\claude_desktop_config.json`

### 2. 添加 MCP 服务配置

在配置文件的 `mcpServers` 部分添加以下内容：

```json
{
  "mcpServers": {
    "claude-memory": {
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

**Windows 用户**请使用：
```json
{
  "mcpServers": {
    "claude-memory": {
      "command": "powershell",
      "args": ["-ExecutionPolicy", "Bypass", "-File", "./mcp/start.ps1"],
      "cwd": ".",
      "env": {
        "PYTHONPATH": "./src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### 3. 重要说明

- **相对路径**：所有路径都是相对于项目目录的相对路径
- **自动识别**：Claude CLI 会自动识别项目中的 `.mcp.json` 文件
- **项目隔离**：每个项目会自动使用独立的项目ID存储记忆

### 4. 验证配置

1. 重启 Claude CLI
2. 在任意项目目录中运行：
   ```bash
   claude
   ```
3. 检查 MCP 服务是否已加载

### 5. 使用示例

配置完成后，在任何项目中都可以使用记忆功能：

```bash
# 搜索记忆
claude mcp claude-memory search_memories --query "错误处理"

# 注入上下文
claude mcp claude-memory inject_context --original_prompt "如何优化性能"

# 跨项目搜索
claude mcp claude-memory cross_project_search --query "数据库设计"
```

## 注意事项

1. **服务依赖**：
   - PostgreSQL（端口 5433）
   - Qdrant（端口 6333）
   - 如果服务未运行，MCP 仍会启动但功能受限

2. **项目ID自动检测顺序**：
   - `.claude.json` 中的 `projectId`
   - 当前目录名
   - Git 仓库名
   - 默认值 "default"

3. **日志文件**：
   - 启动日志：`logs/mcp_startup.log`
   - 服务日志：`logs/mcp_server.log`

## 故障排除

如果服务无法启动，请检查：

1. Python 虚拟环境是否存在：`venv/`
2. 依赖是否已安装：`pip install -r requirements.txt`
3. 日志文件中的错误信息

更多帮助请参考项目 README.md 文档。