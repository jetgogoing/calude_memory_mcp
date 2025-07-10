# Claude CLI 全局配置指南

## 配置 Claude Memory MCP 服务

要在 Claude CLI 中全局使用 Claude Memory 服务，请按照以下步骤配置：

### 1. 找到 Claude CLI 配置文件

配置文件位置：
- **所有平台**: `~/.claude/settings.json`

### 2. 配置 beforeMessage 钩子

在 `~/.claude/settings.json` 文件中添加以下配置：

```json
{
  "hooks": {
    "beforeMessage": {
      "enabled": true,
      "script": "/path/to/claude_memory/scripts/claude_memory_inject.sh --original_prompt \"$MESSAGE\" --injection_mode comprehensive",
      "_comment": "使用快速 HTTP API 注入，响应时间 <0.2秒"
    }
  }
}
```

### 3. 确保脚本可执行

```bash
chmod +x /path/to/claude_memory/scripts/claude_memory_inject.sh
chmod +x /path/to/claude_memory/scripts/fast_inject.py
```

### 4. 重要说明

- **全局共享记忆**：所有对话记忆在全局范围内共享，无项目隔离
- **自动记忆注入**：通过 beforeMessage 钩子自动注入相关历史上下文
- **快速响应**：使用优化的 HTTP API，响应时间低于 0.2 秒

### 5. 验证配置

1. 重启 Claude CLI
2. 在任意项目目录中运行：
   ```bash
   claude
   ```
3. 测试一个简单的命令，检查是否有记忆注入或错误提示

### 6. 监控和日志

- **注入日志**：`~/.claude/logs/claude_memory_injection.log`
  - 记录每次注入的成功/失败状态
  - 包含响应时间和错误信息
  
- **API 服务器日志**：`/tmp/api_server.log`
  - 详细的服务端错误信息
  
- **查看最近的注入日志**：
  ```bash
  tail -f ~/.claude/logs/claude_memory_injection.log
  ```

## 注意事项

1. **服务依赖**：
   - PostgreSQL（端口 5433）
   - Qdrant（端口 6333）
   - 如果服务未运行，MCP 仍会启动但功能受限

2. **记忆管理特性**：
   - 全局共享的记忆池
   - 自动语义检索
   - 智能上下文注入
   - 失败时优雅降级

3. **失败通知**：
   - API 失败时会在输出中显示错误信息
   - 错误信息格式：`[Claude Memory] API 调用失败 (状态码: xxx)`
   - 所有失败都记录在日志文件中

## 故障排除

### 常见问题

1. **"记忆注入服务连接失败"**
   - 确保 API 服务器正在运行：`python -m claude_memory.api_server`
   - 检查端口 8000 是否被占用：`lsof -i :8000`

2. **"API 调用失败 (状态码: 500)"**
   - 查看 API 服务器日志：`tail -100 /tmp/api_server.log`
   - 检查数据库连接是否正常
   - 确保 Qdrant 服务正在运行

3. **"API key not configured"**
   - 检查 `.env` 文件中的 API key 配置
   - 至少需要配置一个模型提供商的 API key

4. **响应超时**
   - 调整 `fast_inject.py` 中的 timeout 参数
   - 检查网络连接和服务器负载

更多帮助请参考项目 README.md 文档。