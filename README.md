# 🧠 Claude Memory - 让 Claude 永远记住你

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-green)](https://modelcontextprotocol.io/)

> 🎯 **无感介入，全局记忆** - 为 Claude CLI 提供持久化的全局知识库，让每次对话都能自然地继承历史上下文

## 🌟 核心特性

### 🚀 完全自动化
- **零配置启动** - 一键安装，自动捕获所有 Claude CLI 对话
- **透明拦截** - 通过 PATH 机制无缝集成，用户无感知
- **智能记忆注入** - 相关历史自动出现在新对话中

### 🛡️ 可靠稳定
- **本地队列备份** - API 故障时零数据丢失
- **全局记忆池** - 跨项目知识共享，无需项目级配置
- **极简设计** - 专注个人使用，避免过度工程

### 🔌 强大集成
- **ZEN MCP Server 支持** - 自动捕获 AI-to-AI 对话
- **多模型兼容** - Gemini、GPT、DeepSeek 等
- **灵活扩展** - 简单的 Hook 机制支持各种集成

## 📦 快速开始

### 系统要求
- Python 3.10+
- Docker & Docker Compose
- Claude CLI 已安装
- 8GB+ RAM

### 一键安装

```bash
# 克隆项目
git clone https://github.com/jetgogoing/claude_memory_mcp
cd claude_memory

# 运行自动安装脚本
./scripts/start_all_services.sh
```

脚本会自动：
- ✅ 启动 PostgreSQL 和 Qdrant 数据库
- ✅ 初始化数据结构
- ✅ 配置 MCP 服务器
- ✅ 安装 Claude 包装器
- ✅ 启动 API 服务

### 验证安装

```bash
# 检查服务状态
python scripts/monitor_status.py

# 测试对话捕获
claude "Hello, test auto-save feature"

# 查看保存的记忆
curl http://localhost:8000/memory/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'
```

## 🏗️ 技术架构

### 系统组成

```
用户输入 "claude ..."
         |
         v
┌─────────────────────┐
│   PATH 优先级拦截    │ (~/.local/bin/claude)
└─────────────────────┘
         |
         v
┌─────────────────────┐     ┌─────────────────┐
│  Claude 包装器      │ --> │  原始 Claude CLI │
│  (捕获对话内容)     │     └─────────────────┘
└─────────────────────┘
         |
         v
┌─────────────────────┐     ┌─────────────────┐
│  API 服务器         │ <-- │  本地队列系统    │
│  (HTTP REST API)    │     │  (故障备份)      │
└─────────────────────┘     └─────────────────┘
         |
         v
┌─────────────────────┐     ┌─────────────────┐
│  PostgreSQL         │     │  Qdrant          │
│  (结构化存储)       │     │  (向量数据库)    │
└─────────────────────┘     └─────────────────┘
         |
         v
┌─────────────────────┐
│  MCP Server         │
│  (记忆注入)         │
└─────────────────────┘
```

### 核心流程

1. **对话捕获** - 包装器透明拦截 Claude 命令，捕获输入输出
2. **智能解析** - 清理 ANSI 控制字符，提取纯文本内容
3. **可靠存储** - 通过 API 存储到数据库，失败时保存到本地队列
4. **向量化处理** - 使用 Qwen3 生成 4096 维向量用于语义搜索
5. **记忆注入** - MCP 服务器自动注入相关历史到新对话

## 🔧 配置说明

### 环境变量

创建 `.env` 文件：

```bash
# 数据库配置
DATABASE__DATABASE_URL=postgresql+asyncpg://claude_memory:password@localhost:5433/claude_memory
DATABASE__POOL_SIZE=20

# Qdrant 配置
QDRANT__QDRANT_URL=http://localhost:6333
QDRANT__COLLECTION_NAME=claude_memories
QDRANT__VECTOR_SIZE=4096

# 模型 API 配置
MODELS__SILICONFLOW_API_KEY=your_key  # Qwen3 嵌入模型
MODELS__GEMINI_API_KEY=your_key       # Gemini 压缩模型

# 性能优化
PERFORMANCE__BATCH_SIZE=50
PERFORMANCE__MAX_CONCURRENT_REQUESTS=20
```

### 控制选项

```bash
# 临时禁用自动保存
export CLAUDE_MEMORY_DISABLE=1

# 启用调试模式
export CLAUDE_MEMORY_DEBUG=1

# 自定义 API 地址
export CLAUDE_MEMORY_API_URL=http://your-server:8000
```

## 📊 使用示例

### 基础对话

```bash
# 普通使用，对话自动保存
claude "解释一下 Python 的装饰器"

# 引用历史记忆
claude "继续刚才关于装饰器的讨论"
```

### 搜索记忆

```python
# 通过 API 搜索
import requests

response = requests.post(
    "http://localhost:8000/memory/search",
    json={
        "query": "装饰器",
        "limit": 5,
        "project_id": "global"
    }
)
```

### 查看状态

```bash
# 监控系统状态
python scripts/monitor_status.py

# 查看队列
ls ~/.claude_memory/queue/

# 查看日志
tail -f ~/.claude_memory/wrapper_v2.log
```

## 🔌 ZEN MCP Server 集成

### 自动安装

```bash
cd /path/to/claude_memory
./scripts/install_zen_capture.sh /path/to/zen-mcp-server
```

### 功能特性

- 🤖 自动捕获所有 AI-to-AI 对话
- 📊 记录模型参数和元数据
- 🔄 API 故障时本地队列备份
- 🎛️ 环境变量灵活控制

详见 [ZEN 集成指南](docs/ZEN_MCP_SERVER_INTEGRATION.md)

## 🛠️ 运维管理

### 健康检查

```bash
# API 健康状态
curl http://localhost:8000/health

# 数据库状态
curl http://localhost:8000/status
```

### 数据维护

```bash
# 备份数据
pg_dump -h localhost -p 5433 -U claude_memory -d claude_memory > backup.sql

# 处理队列
python scripts/queue_processor.py

# 清理日志
python scripts/log_cleaner.py
```

### 故障排查

1. **对话未保存**
   - 检查包装器：`which claude`
   - 查看日志：`tail -f ~/.claude_memory/wrapper_v2.log`
   - 验证 API：`curl http://localhost:8000/health`

2. **记忆注入失败**
   - 检查 MCP 配置：`cat ~/.claude/settings.json`
   - 验证向量数据库：`curl http://localhost:6333/collections`

3. **性能问题**
   - 监控队列大小：`ls ~/.claude_memory/queue/ | wc -l`
   - 检查 API 延迟：查看 `wrapper_v2.log` 中的时间戳

## 📈 性能指标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 包装器延迟 | 4.2ms | <10ms |
| API 响应时间 | 35s | <30s |
| 对话捕获率 | 99% | >99% |
| 记忆注入延迟 | 200ms | <500ms |
| 系统可用性 | 99.5% | >99% |

## 🚀 发展历程

### 主要里程碑

1. **全局记忆池架构** (v2.0)
   - 从项目隔离到全局共享
   - 简化配置，提升用户体验

2. **自动保存功能** (v2.1)
   - PATH 拦截机制
   - 本地队列可靠性保证

3. **ZEN 集成** (v2.2)
   - AI-to-AI 对话捕获
   - 零侵入设计

### 未来规划

- [ ] 交互模式支持（PTY 实现）
- [ ] 批量 API 提交优化
- [ ] Web UI 管理界面
- [ ] 更多 AI 工具集成

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发环境

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
python test_wrapper_unit.py

# 代码检查
black src/
mypy src/
```

### 提交规范

- feat: 新功能
- fix: 错误修复
- docs: 文档更新
- perf: 性能优化
- refactor: 代码重构

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [Anthropic](https://anthropic.com) - MCP 协议
- [Qdrant](https://qdrant.tech) - 向量数据库
- [QwenLM](https://github.com/QwenLM/Qwen) - 嵌入模型

---

<div align="center">
  <p>让 Claude 成为真正了解你的 AI 助手</p>
  <p>
    <a href="https://github.com/jetgogoing/claude_memory_mcp/issues">报告问题</a> •
    <a href="https://github.com/jetgogoing/claude_memory_mcp/discussions">参与讨论</a>
  </p>
</div>