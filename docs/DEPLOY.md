# Claude Memory MCP 服务部署指南

## 🎯 目标
为个人用户在Ubuntu 22.04上部署Claude Memory MCP服务，让Claude CLI能够使用记忆管理功能。

## 📋 前置要求

1. **系统环境**
   - Ubuntu 22.04
   - Python 3.10+
   - 至少4GB RAM

2. **已安装软件**
   - Claude CLI (已配置并可用)
   - Docker (用于Qdrant)

3. **API密钥** (如需完整功能)
   - GEMINI_API_KEY
   - SILICONFLOW_API_KEY
   - OPENROUTER_API_KEY

## 🚀 快速部署步骤

### 1. 启动Qdrant向量数据库

```bash
# 如果Qdrant未运行，使用Docker启动
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/data/qdrant:/qdrant/storage \
  qdrant/qdrant
```

### 2. 设置Python环境

```bash
# 进入项目目录
cd /home/jetgogoing/claude_memory

# 激活虚拟环境
source venv-claude-memory/bin/activate

# 安装依赖（如未安装）
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件：

```bash
cat > .env << EOF
# 基础配置
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# API密钥（可选，用于完整功能）
GEMINI_API_KEY=your_key_here
SILICONFLOW_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here

# 日志配置
LOG_LEVEL=INFO
EOF
```

### 4. 部署MCP服务

运行部署脚本：

```bash
python deploy_simple.py
```

### 5. 验证部署

重启Claude CLI并测试：

```bash
# 在Claude CLI中
/mcp                          # 查看所有MCP服务
/mcp claude-memory memory_status  # 测试服务状态
```

## 📁 项目结构

```
claude_memory/
├── simple_mcp_server.py      # 简化的MCP服务器
├── deploy_simple.py          # 部署脚本
├── .env                      # 环境配置
├── data/
│   └── qdrant/              # Qdrant数据存储
└── logs/                     # 服务日志
```

## 🛠️ 管理脚本

### 启动服务
```bash
# Qdrant已在Docker中运行
# MCP服务由Claude CLI自动管理
```

### 查看日志
```bash
tail -f logs/mcp_server.log
```

### 停止服务
```bash
# 停止Qdrant
docker stop qdrant

# MCP服务会在Claude CLI退出时自动停止
```

## ❓ 常见问题

### 1. MCP服务显示failed

**原因**: 日志输出干扰了stdio通信

**解决**: 使用 `simple_mcp_server.py`，它会静默所有输出

### 2. 找不到工具

**症状**: `/mcp` 没有显示 claude-memory

**解决**: 
- 确保运行了 `deploy_simple.py`
- 重启Claude CLI

### 3. Qdrant连接失败

**检查**: 
```bash
curl http://localhost:6333/collections
```

**解决**: 确保Qdrant在6333端口运行

## 🎯 使用示例

在Claude CLI中：

```bash
# 搜索记忆
/mcp claude-memory memory_search query="Python异步编程"

# 检查服务状态  
/mcp claude-memory memory_status
```

## 📈 后续优化

1. **完整功能集成**
   - 连接实际的语义搜索
   - 实现记忆压缩和存储
   - 添加上下文注入

2. **性能优化**
   - 添加缓存机制
   - 优化向量检索

3. **监控和维护**
   - 添加健康检查
   - 日志轮转
   - 资源监控

## 🤝 支持

如遇到问题：
1. 查看日志: `logs/mcp_server.log`
2. 检查Qdrant状态
3. 确认Claude CLI配置: `~/.claude.json`

---

✨ 简单、稳定、可用 - 专注核心功能的Claude记忆管理服务