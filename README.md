# 🧠 Claude Memory MCP Service

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-green)](https://modelcontextprotocol.io/)

一个为 Claude CLI 提供全局记忆管理的 MCP (Model Context Protocol) 服务。通过语义检索自动为每次对话注入相关的历史上下文。

## 🎯 核心功能

- **全局记忆共享**: 所有对话记忆全局共享，无项目隔离
- **自动记忆存储**: 自动保存所有 Claude 对话历史
- **语义检索**: 使用向量数据库进行智能记忆检索
- **无感上下文注入**: 自动为新对话注入相关历史记忆

## 🚀 快速开始

### 系统要求

- Python 3.10+
- Docker & Docker Compose
- PostgreSQL (端口 5433)
- Qdrant (端口 6333)

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-username/claude-memory.git
cd claude-memory

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置 API 密钥

# 3. 启动服务
docker compose up -d

# 4. 初始化数据库
python scripts/init_database_tables.py

# 5. 启动 MCP 服务器
python -m claude_memory.mcp_server
```

### 配置 Claude CLI

在 `~/.config/claude/config.json` 中添加：

```json
{
  "mcp": {
    "servers": {
      "claude-memory": {
        "command": "/path/to/claude-memory/venv/bin/python",
        "args": ["-m", "claude_memory.mcp_server"],
        "env": {
          "PYTHONPATH": "/path/to/claude-memory/src"
        }
      }
    }
  }
}
```

## 📖 使用说明

### 基本使用

1. 启动 Claude CLI：`claude`
2. 所有对话自动保存并建立索引
3. 新对话会自动注入相关历史记忆

### 必需的 API 密钥

在 `.env` 文件中至少配置一个：

```bash
# OpenRouter (推荐)
OPENROUTER_API_KEY=your-api-key

# Google Gemini
GEMINI_API_KEY=your-api-key

# SiliconFlow
SILICONFLOW_API_KEY=your-api-key
```

## 🏗️ 项目结构

```
claude-memory/
├── src/claude_memory/      # 核心源代码
│   ├── mcp_server.py      # MCP 协议实现
│   ├── collectors/        # 对话收集器
│   ├── processors/        # 语义压缩器
│   ├── retrievers/        # 记忆检索器
│   └── injectors/         # 上下文注入器
├── docker-compose.yml     # Docker 配置
└── scripts/               # 工具脚本
```

## 🛠️ 运维管理

### 服务管理

```bash
# 查看服务状态
docker ps

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down
```

### 数据库维护

```bash
# 连接 PostgreSQL
psql -h localhost -p 5433 -U claude_memory -d claude_memory

# 查看 Qdrant 状态
curl http://localhost:6333/collections
```

## 🔧 故障排除

### 常见问题

1. **MCP 服务器启动失败**
   - 检查端口占用：PostgreSQL (5433), Qdrant (6333)
   - 验证 Python 环境和依赖安装

2. **记忆检索无结果**
   - 确认 API 密钥配置正确
   - 检查 Qdrant 服务是否运行
   - 调整搜索评分阈值（默认 0.3）

3. **数据库连接错误**
   - 确认 PostgreSQL 在 5433 端口运行
   - 检查数据库初始化是否完成

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。