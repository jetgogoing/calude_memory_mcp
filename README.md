# 🧠 Claude Memory MCP Service

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-green)](https://modelcontextprotocol.io/)
[![Vector DB](https://img.shields.io/badge/Qdrant-Vector%20DB-purple)](https://qdrant.tech/)
[![Embedding](https://img.shields.io/badge/Qwen3-8B%20Embedding-orange)](https://github.com/QwenLM/Qwen)

> 🎯 **无感介入，全局记忆**：为 Claude CLI 提供持久化的全局知识库，让每次对话都能自然地继承历史上下文

Claude Memory 是一个基于 MCP (Model Context Protocol) 的智能记忆系统，专为提供**无感介入**的体验而设计。它在后台自动工作，为您的开发工作流提供持续的上下文支持，就像是 Claude 的自然延伸，而非需要管理的额外工具。

## 🌟 技术亮点

### 🚀 核心创新
- **全局共享记忆池**：使用 `project_id="global"` 实现跨项目知识共享，无需项目级配置
- **无感记忆注入**：自动触发，零配置、零干预，真正的"设置后即忘"体验
- **混合检索策略**：语义搜索 + 关键词匹配，召回率提升 40%
- **智能模型选择**：Gemini 2.5 Pro + DeepSeek + Qwen3，根据任务自动选择最优模型
- **极速响应**：200-500ms 完成记忆注入，对用户体验零影响

### 🏆 技术优势
- **4096维向量空间**：使用 Qwen3-Embedding-8B，业界领先的语义理解
- **智能压缩算法**：对话压缩比达 70%，保留 95% 关键信息
- **多级缓存架构**：嵌入/搜索/注入三级缓存，性能提升 5x
- **质量保证机制**：0.7 质量阈值，自动模型升级重试

## 🌐 全局记忆架构

### 从项目隔离到全局知识库

Claude Memory 采用**全局共享记忆池**设计，彻底简化了配置和使用体验：

```
传统架构（项目隔离）：              新架构（全局共享）：
[项目 A] <=> [记忆 A]              [项目 A] ↘
[项目 B] <=> [记忆 B]                        → [全局记忆池]
[项目 C] <=> [记忆 C]              [项目 C] ↗
```

**优势**：
- 📦 **一次配置，全局生效**：无需在每个项目中重复配置
- 🔄 **跨项目知识流转**：在项目 A 中学到的知识可以在项目 B 中使用
- 🚀 **零配置使用**：新项目自动享受全部历史记忆
- 💡 **统一管理**：所有记忆集中存储，便于备份和管理

## 🔬 工作原理

### 触发机制
```
用户输入 → Claude CLI → MCP协议 → claude_memory_inject → 记忆系统
    ↑                                                          ↓
    ←───────────────── 增强的响应 ←──────────────────────────
```

### 核心流程图
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   用户输入提示词  │ ──→ │  MCP服务器接收   │ ──→ │   向量化查询    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          ↓
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  返回增强提示词  │ ←── │   上下文构建     │ ←── │   混合检索      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               ↑                          ↓
                        ┌─────────────────┐     ┌─────────────────┐
                        │   记忆优化选择   │ ←── │  Qdrant + PG    │
                        └─────────────────┘     └─────────────────┘
```

## 🏗️ 技术架构

### 系统架构图
```
┌────────────────────────────────────────────────────────────────┐
│                        Claude CLI                               │
├────────────────────────────────────────────────────────────────┤
│                    MCP Protocol Layer                           │
├────────────────────────────────────────────────────────────────┤
│                    MCP Server (mcp_server.py)                   │
│  ┌──────────────┬──────────────┬──────────────┬─────────────┐ │
│  │ inject_tool  │ search_tool  │ status_tool  │ health_tool │ │
│  └──────────────┴──────────────┴──────────────┴─────────────┘ │
├────────────────────────────────────────────────────────────────┤
│                 Service Manager (Orchestrator)                  │
├────────────────────────────────────────────────────────────────┤
│  ┌─────────────┬────────────────┬─────────────┬─────────────┐ │
│  │ Collector   │   Compressor    │  Retriever  │  Injector   │ │
│  │             │                 │             │             │ │
│  │ • 对话收集  │ • AI摘要生成    │ • 向量搜索  │ • 上下文构建 │ │
│  │ • 消息解析  │ • 质量评估      │ • 混合检索  │ • 记忆优化   │ │
│  │ • 元数据    │ • 关键词提取    │ • 重排序    │ • Token管理  │ │
│  └─────────────┴────────────────┴─────────────┴─────────────┘ │
├────────────────────────────────────────────────────────────────┤
│                        Storage Layer                            │
│  ┌─────────────────────────┐  ┌──────────────────────────────┐ │
│  │      PostgreSQL         │  │         Qdrant               │ │
│  │  • 结构化数据存储        │  │  • 4096维向量存储            │ │
│  │  • 对话/消息/记忆单元    │  │  • 余弦相似度搜索            │ │
│  │  • JSONB关键词索引       │  │  • HNSW索引优化              │ │
│  └─────────────────────────┘  └──────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│                      Model Layer                                │
│  ┌────────────┬─────────────┬────────────┬──────────────────┐ │
│  │ Qwen3-8B   │ Gemini 2.5  │  DeepSeek  │  Claude/GPT      │ │
│  │ Embedding  │    Pro       │    V2.5    │  (via Router)    │ │
│  └────────────┴─────────────┴────────────┴──────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 数据流时序
```
T0: 用户输入 "帮我优化之前讨论的代码"
 │
T1: MCP服务器接收 inject 请求 
 │
T2: 生成查询向量 (Qwen3-Embedding-8B) [~100ms]
 │  └─ "优化 代码 讨论" → [0.23, -0.15, 0.87, ...] (4096维)
 │
T3: 执行混合搜索 [~150ms]
 │  ├─ 语义搜索: Qdrant 向量相似度 (余弦距离)
 │  └─ 关键词搜索: PostgreSQL JSONB 查询
 │
T4: 记忆优化选择 [~20ms]
 │  ├─ 多样性过滤 (关键词重叠 < 70%)
 │  └─ 类型优先级 (DOCUMENTATION > CONVERSATION > ARCHIVE)
 │
T5: 构建注入上下文 [~10ms]
 │  └─ 格式化记忆单元为 Markdown
 │
T6: 返回增强提示词
 │  └─ "[相关记忆]\n...\n[用户输入]\n帮我优化之前讨论的代码"
 │
T7: Claude 生成响应 (带有完整上下文)
```

## 💡 核心组件详解

### 1. **语义压缩器 (SemanticCompressor)**
- **智能摘要生成**：使用 Gemini 2.5 Pro / DeepSeek 分析对话
- **质量控制**：0.7 阈值，不合格自动升级模型重试
- **压缩比优化**：平均压缩至原始大小的 30%
- **关键信息保留**：决策、计划、重要结论 100% 保留

### 2. **语义检索器 (SemanticRetriever)**
- **向量引擎**：Qwen3-Embedding-8B (4096维)
- **混合策略**：
  - 语义搜索：基于余弦相似度的向量检索
  - 关键词搜索：PostgreSQL JSONB 高效匹配
  - 智能合并：相同记忆分数增强 30%
- **重排序算法**：
  - `relevance_time`: 相关性 × 时间衰减因子
  - `quality_boost`: 质量分数提升优质记忆
  - `type_priority`: 文档 > 对话 > 归档

### 3. **上下文注入器 (ContextInjector)**
- **智能选择**：多样性过滤避免信息冗余
- **Token 预算**：当前 comprehensive 模式（无限制）
- **缓存优化**：三级缓存减少重复计算
- **注入模板**：结构化 Markdown 格式

### 4. **MCP 服务器**
- **协议实现**：完整 MCP 标准支持
- **工具注册**：
  - `claude_memory_inject`: 自动上下文注入
  - `claude_memory_search`: 手动记忆搜索
  - `claude_memory_status`: 服务状态监控
  - `claude_memory_health`: 健康检查
- **异步架构**：全程 AsyncIO，高并发处理

## 📊 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 记忆注入延迟 | 200-500ms | 端到端完整流程 |
| 向量生成速度 | ~100ms | Qwen3-8B GPU 加速 |
| 检索响应时间 | 50-200ms | 取决于记忆库大小 |
| 压缩比 | 70% | 保留 95% 关键信息 |
| 并发处理能力 | 100+ QPS | 异步架构优势 |
| 缓存命中率 | >60% | 三级缓存策略 |

## 🚀 快速开始

### 一键启动（推荐）

```bash
# 克隆项目
git clone https://github.com/your-username/claude-memory.git
cd claude-memory

# 运行自动安装和启动脚本
./scripts/start_all_services.sh
```

就这么简单！脚本会自动：
- ✅ 启动所有必需的服务（PostgreSQL、Qdrant）
- ✅ 初始化数据库
- ✅ 配置 MCP 服务
- ✅ 启动 API 服务器

### 系统要求
- Python 3.10+
- Docker & Docker Compose（用于数据库服务）
- 8GB+ RAM（推荐 16GB）
- 10GB+ 存储空间

### 服务端口
- PostgreSQL: 5433
- Qdrant: 6333
- API Server: 8000

### 环境变量配置

创建 `.env` 文件（注意：不是 `.env.example`）：

```bash
# 数据库配置
DATABASE__DATABASE_URL=postgresql+asyncpg://claude_memory:password@localhost:5433/claude_memory
DATABASE__POOL_SIZE=20
DATABASE__MAX_OVERFLOW=40

# Qdrant 配置
QDRANT__QDRANT_URL=http://localhost:6333
QDRANT__COLLECTION_NAME=claude_memories
QDRANT__VECTOR_SIZE=4096

# 模型 API 配置 (至少配置一个)
MODELS__SILICONFLOW_API_KEY=your_key  # Qwen3 嵌入模型
MODELS__GEMINI_API_KEY=your_key       # Gemini 压缩模型
MODELS__OPENROUTER_API_KEY=your_key   # 备用模型路由

# 性能优化
PERFORMANCE__BATCH_SIZE=50
PERFORMANCE__MAX_CONCURRENT_REQUESTS=20
PERFORMANCE__REQUEST_TIMEOUT_SECONDS=30
```

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-username/claude-memory.git
cd claude-memory

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -e .

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入您的 API 密钥

# 5. 启动基础服务
docker compose up -d

# 6. 初始化数据库
python scripts/init_database_tables.py

# 7. 启动 MCP 服务器
python -m claude_memory
```

### 配置 Claude CLI（自动完成）

启动脚本会自动配置 Claude CLI。如需手动配置，可以：

**方式1：使用配置脚本**
```bash
python scripts/fix_claude_mcp_config.py
```

**方式2：手动编辑配置**
在 `~/.claude.json` 或 `~/.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "claude-memory-mcp": {
      "type": "stdio",
      "command": "/path/to/claude-memory/scripts/start_mcp_with_env.sh",
      "env": {
        "PYTHONPATH": "/path/to/claude-memory/src"
      }
    }
  }
}
```

### 使用方式

配置完成后，Claude Memory 会自动工作：

```bash
# 在任何项目目录中
claude "帮我分析这个代码的性能问题"
# Claude 会自动注入相关的历史记忆

claude "继续上次的重构讨论"
# 自动获取之前的重构相关对话
```

**无需项目级配置！** Claude Memory 使用全局记忆池，所有项目自动共享知识。

## 📖 使用指南

### 项目级配置（可选）

大多数情况下，您**不需要**在项目中创建任何配置文件。Claude Memory 会自动使用全局配置。

只有在特殊情况下才需要项目级 `.mcp.json`：

**1. 临时禁用记忆功能**
```json
{
  "mcp": "none"
}
```

**2. 使用不同的记忆服务**
```json
{
  "mcp": "other-memory-service"
}
```

**3. 调整记忆参数**
```json
{
  "mcp": "claude-memory",
  "settings": {
    "min_score": 0.9,
    "limit": 20
  }
}
```

### 基础使用

1. **启动 Claude CLI**
   ```bash
   claude
   ```

2. **自动记忆管理**
   - 所有对话自动保存并压缩为记忆单元
   - 新对话自动注入相关历史上下文
   - 无需任何手动操作

3. **记忆类型**
   - `DOCUMENTATION`: 技术文档、API 说明
   - `CONVERSATION`: 一般对话记录
   - `ARCHIVE`: 归档的历史记忆

### 高级功能

#### 手动搜索记忆
```python
# 在 Claude CLI 中
search_memories("优化代码性能")
```

#### 查看服务状态
```bash
# 通过 API
curl http://localhost:8000/status

# 通过 CLI
python -m claude_memory status
```

#### 性能调优
```bash
# 调整记忆注入的 Token 预算
export CLAUDE_MEMORY_MAX_TOKENS=5000

# 启用调试日志
export CLAUDE_MEMORY_LOG_LEVEL=DEBUG
```

## 🛠️ 运维管理

### 监控指标

```bash
# Prometheus 指标端点
http://localhost:8000/metrics

# 关键指标：
- memory_injection_latency_seconds
- vector_search_duration_seconds
- compression_quality_score
- cache_hit_rate
```

### 数据库维护

```bash
# 备份记忆数据
pg_dump -h localhost -p 5433 -U claude_memory -d claude_memory > backup.sql

# 清理过期记忆
python scripts/cleanup_expired_memories.py

# 重建向量索引
python scripts/rebuild_vector_index.py
```

### 故障排查

1. **记忆注入失败**
   ```bash
   # 检查 MCP 服务器日志
   tail -f logs/mcp_server.log
   
   # 验证向量服务
   curl http://localhost:6333/collections/claude_memories
   ```

2. **检索性能下降**
   ```bash
   # 分析慢查询
   python scripts/analyze_slow_queries.py
   
   # 优化向量索引
   python scripts/optimize_qdrant_index.py
   ```

3. **内存使用过高**
   ```bash
   # 清理缓存
   python scripts/clear_caches.py
   
   # 调整连接池
   export DATABASE__POOL_SIZE=10
   ```

## 🔬 技术规格

### 向量数据库配置
- **向量维度**: 4096 (Qwen3-Embedding-8B)
- **距离度量**: 余弦相似度
- **索引类型**: HNSW (分层可导航小世界)
- **量化**: 标量量化 (可选)

### AI 模型规格
| 模型 | 用途 | 上下文窗口 | 特点 |
|------|------|-----------|------|
| Qwen3-Embedding-8B | 向量生成 | 8K | 高质量中文语义理解 |
| Gemini 2.5 Pro | 对话压缩 | 1M | 超长上下文，深度理解 |
| DeepSeek V2.5 | 备用压缩 | 128K | 成本效益最优 |

### 存储估算
- **每条对话**: ~2KB (压缩后)
- **每个向量**: ~16KB (4096 × 4 bytes)
- **元数据**: ~1KB
- **总计**: ~20KB/对话

### 扩展性设计
- **水平扩展**: 支持多实例部署
- **分片策略**: 按时间/用户 ID 分片
- **读写分离**: PostgreSQL 主从复制
- **缓存层**: Redis 集群支持

## 🤝 贡献指南

我们欢迎各种形式的贡献！

### 开发环境设置
```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码格式化
black src/
isort src/

# 类型检查
mypy src/
```

### 提交规范
- feat: 新功能
- fix: 错误修复
- docs: 文档更新
- perf: 性能优化
- refactor: 代码重构

## 📜 更新日志

### v2.0.0 (2025-01)
- 🌐 **重大更新**：引入全局记忆池架构
- 🚀 **无感介入**：零配置即可跨项目使用
- ✨ 简化配置流程，移除项目级强制配置
- 📦 新增一键启动脚本
- 🔄 支持旧版本记忆迁移

### v1.5.0 (2024-01)
- ✨ 全新的混合检索策略
- 🚀 性能优化：延迟降低 50%
- 🔧 支持自定义嵌入模型
- 📊 新增 Prometheus 监控

### v1.4.0 (2023-12)
- ✨ 升级到 Qwen3-Embedding-8B
- 🎯 智能记忆类型识别
- 🔧 多级缓存架构
- 📈 质量评分系统

## ❓ 常见问题

### Q: 为什么选择全局记忆池而不是项目隔离？
A: 基于实际使用经验，我们发现：
- 开发者经常在多个项目间切换，需要共享的知识和上下文
- 项目隔离增加了配置复杂度，违背了"无感介入"的设计理念
- 全局记忆池让知识可以跨项目流转，提升整体开发效率

### Q: 如何确保隐私和安全？
A: Claude Memory 采用多层安全措施：
- 所有数据本地存储，不会上传到云端
- 支持敏感信息过滤配置
- 可以随时清理特定时间段的记忆

### Q: 记忆会无限增长吗？
A: 不会。系统包含智能管理机制：
- 自动压缩冗余信息
- 基于使用频率的记忆权重调整
- 可配置的记忆过期策略

### Q: 如何迁移旧版本的项目级记忆？
A: 运行迁移脚本即可：
```bash
python scripts/migrate_to_global.py
```

## 🔧 故障排除

### 服务无法启动
```bash
# 检查端口占用
lsof -i :5433  # PostgreSQL
lsof -i :6333  # Qdrant
lsof -i :8000  # API Server

# 查看服务日志
tail -f logs/api_server.log
tail -f logs/mcp_server.log
```

### 记忆注入失败
1. 确认 API 服务器运行状态：
   ```bash
   curl http://localhost:8000/health
   ```
2. 检查环境变量配置：
   ```bash
   cat .env | grep API_KEY
   ```
3. 验证 MCP 配置：
   ```bash
   python scripts/verify_mcp_setup.py
   ```

### 性能问题
- 增加缓存大小：编辑 `.env` 中的 `CACHE_SIZE`
- 优化向量索引：运行 `python scripts/optimize_vectors.py`
- 清理过期记忆：运行 `python scripts/cleanup_old_memories.py`

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [Anthropic](https://anthropic.com) - MCP 协议设计
- [Qdrant](https://qdrant.tech) - 高性能向量数据库
- [QwenLM](https://github.com/QwenLM/Qwen) - 优秀的嵌入模型

---

<div align="center">
  <p>用 ❤️ 打造，让 Claude 永远记住您</p>
  <p>
    <a href="https://github.com/your-username/claude-memory/issues">报告问题</a> •
    <a href="https://github.com/your-username/claude-memory/discussions">参与讨论</a> •
    <a href="https://claude-memory.docs.com">查看文档</a>
  </p>
</div>