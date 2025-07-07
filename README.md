# Claude Memory MCP Service

> 为Claude CLI提供长期记忆和智能上下文注入能力的完整MCP服务

## 🎯 核心功能

- **自动对话采集**: 实时捕获Claude CLI的输入输出对话
- **智能语义压缩**: 使用多模型协作生成高质量记忆单元
- **向量语义检索**: 基于Qdrant的高性能相似度搜索
- **上下文智能注入**: 动态构建增强提示词，支持Token预算控制
- **跨项目记忆共享**: 支持项目间对话记忆的全局共享

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Memory MCP Service                    │
├─────────────────────────────────────────────────────────────────┤
│  数据采集层  │ Collectors + 对话解析 + 数据标准化               │
├─────────────────────────────────────────────────────────────────┤
│  语义处理层  │ Processors + Fusers + 向量化 + 质量验证         │
├─────────────────────────────────────────────────────────────────┤
│  存储检索层  │ Database + Retrievers + Qdrant + 缓存机制       │
├─────────────────────────────────────────────────────────────────┤
│  智能注入层  │ Injectors + Builders + Token控制 + 降级策略     │
└─────────────────────────────────────────────────────────────────┘
         ↕
┌─────────────────────────────────────────────────────────────────┐
│  服务管理层  │ Managers + Monitors + 配置管理 + 错误处理       │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
claude-memory/
├── src/claude_memory/               # 核心服务代码
│   ├── builders/                   # 提示构建器
│   ├── collectors/                 # 对话采集器
│   ├── processors/                 # 语义处理器
│   ├── fusers/                     # 记忆融合器
│   ├── retrievers/                 # 语义检索器
│   ├── injectors/                  # 上下文注入器
│   ├── managers/                   # 服务管理器
│   ├── monitors/                   # 成本监控器
│   ├── limiters/                   # Token限制器
│   ├── database/                   # 数据库管理
│   ├── models/                     # 数据模型
│   ├── utils/                      # 工具函数
│   └── mcp_server.py              # MCP服务器
├── global/                         # 🌐 全局部署模块
│   ├── src/global_mcp/            # 跨项目部署版本
│   ├── docker/                    # 容器化配置
│   ├── scripts/                   # 安装脚本
│   └── tests/                     # 性能测试
├── scripts/                        # 管理和维护脚本
├── config/                         # 配置文件
├── docs/                          # 📚 完整文档中心
├── tests/                         # 测试套件
├── logs/                          # 日志文件
└── data/                          # 数据存储
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Claude CLI 已安装
- Docker (可选)
- Qdrant 向量数据库 (自动配置)

### 本地开发部署

```bash
# 1. 激活虚拟环境
source venv-claude-memory/bin/activate

# 2. 启动服务组件
./start.sh

# 3. 验证服务状态
python scripts/comprehensive_health_check.py
```

### 全局跨项目部署

如果你需要在多个项目间共享记忆，使用全局部署模块：

```bash
# 进入全局部署目录
cd global/

# 一键安装部署
chmod +x install.sh
./install.sh

# 或使用Docker容器化部署
docker-compose -f docker-compose.global.yml up -d
```

## 📊 性能指标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 语义检索延迟 | 45ms | ≤ 150ms |
| 端到端处理延迟 | 180ms | ≤ 300ms |
| 记忆检索准确率 | 92% | ≥ 90% |
| 服务可用性 | 99.7% | ≥ 99.5% |
| 并发支持 | 15个会话 | ≥ 10个会话 |

## 📚 文档中心

我们提供了完整的文档体系，所有详细文档都在 [`docs/`](docs/) 文件夹中：

### 📖 完整指南
- **[部署指南](docs/DEPLOYMENT_GUIDE.md)** - 详细的部署指南，包含开发、生产、企业级部署
- **[使用示例](docs/USAGE_EXAMPLES.md)** - 详细使用示例和最佳实践  
- **[API参考](docs/API_REFERENCE.md)** - 完整的API接口文档
- **[项目总结](docs/PROJECT_SUMMARY.md)** - 项目成就和技术总结

### 📋 运维文档
- **[运维手册](docs/OPERATIONS_RUNBOOK.md)** - 日常运维和故障处理
- **[快速参考](docs/QUICK_REFERENCE.md)** - 常用命令和配置
- **[脚本索引](docs/SCRIPTS_INDEX.md)** - 管理脚本说明

### 📝 项目记录
- **[会话记录](docs/sessions/)** - 开发会话和决策记录
- **[文档导航](docs/README.md)** - 完整文档索引

## 🔧 MCP工具

### 核心工具

| 工具名 | 功能 | 示例 |
|--------|------|------|
| `search_memories` | 搜索历史记忆 | 查找相关技术讨论 |
| `inject_context` | 注入智能上下文 | 增强当前对话 |
| `health_check` | 系统健康检查 | 验证服务状态 |
| `get_stats` | 获取性能统计 | 监控系统性能 |

### 使用示例

```bash
# 搜索相关记忆
claude mcp claude-memory search_memories --query "Python性能优化"

# 健康检查
claude mcp claude-memory health_check

# 获取统计信息
claude mcp claude-memory get_stats
```

## 🛠️ 开发指南

### 代码质量标准

- **类型注解**: 全面的类型提示和检查
- **文档规范**: 完整的docstring和注释
- **测试覆盖**: 单元测试 + 集成测试
- **性能监控**: 实时性能指标收集

### 运行测试

```bash
# 运行测试套件
python -m pytest tests/

# 性能测试
python tests/performance/

# 集成测试
python tests/integration/
```

### 监控和维护

```bash
# 启动监控
python scripts/monitoring.py

# 数据库维护
python scripts/db_maintenance.py

# 成本监控
python scripts/cost_capacity_monitor.py
```

## 🌐 全局部署特性

### 跨项目记忆共享

`global/` 模块提供了标准化的全局部署能力：

- **零配置部署**: 一键安装脚本
- **容器化支持**: Docker部署
- **跨项目兼容**: 项目A的记忆可在项目B中使用
- **高性能优化**: 并发处理，智能缓存

详见：[全局部署文档](docs/DEPLOYMENT_GUIDE.md)

## 🔍 故障排除

### 常见问题

1. **MCP服务启动失败**
   ```bash
   # 检查日志
   tail -f logs/mcp_server.log
   
   # 重启服务
   ./stop.sh && ./start.sh
   ```

2. **向量数据库连接问题**
   ```bash
   # 检查Qdrant状态
   ./scripts/start_qdrant.sh
   
   # 验证连接
   python scripts/verify_mcp_setup.py
   ```

3. **性能问题诊断**
   ```bash
   # 性能分析
   python scripts/mcp_diagnostic.py
   
   # 健康检查
   python scripts/comprehensive_health_check.py
   ```

## 📈 监控和告警

- **实时监控**: Prometheus指标收集
- **性能告警**: 延迟、错误率阈值告警
- **成本控制**: API调用预算监控
- **健康检查**: 多层次服务状态检测

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

感谢Claude Code团队提供优秀的MCP框架，使得这个项目成为可能。

---

**🎯 探索智能记忆管理的无限可能！**