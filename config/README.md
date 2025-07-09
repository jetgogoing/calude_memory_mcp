# 配置管理指南

## 概述

Claude Memory MCP Service 使用分层配置策略，针对不同使用场景提供优化的配置模板。

## 配置文件说明

### 1. `.env.minimal` - 最小化配置
- **用途**：快速启动、本地测试、初次体验
- **特点**：仅包含必要配置项，约 30 行
- **使用方法**：
  ```bash
  cp .env.minimal .env
  # 编辑 .env，填入至少一个 API 密钥
  docker compose up -d
  ```

### 2. `.env.development` - 开发环境配置
- **用途**：本地开发、功能测试、调试
- **特点**：
  - 启用调试模式和详细日志
  - 包含所有 API 密钥示例
  - 使用宽松的安全策略
- **使用方法**：
  ```bash
  cp .env.development .env
  docker compose up -d
  ```

### 3. `.env.production` - 生产环境配置
- **用途**：正式部署、生产环境
- **特点**：
  - 优化的性能参数
  - 严格的安全配置
  - 从环境变量读取敏感信息
- **使用方法**：
  ```bash
  cp .env.production .env
  # 设置环境变量
  export POSTGRES_PASSWORD="your_secure_password"
  export SILICONFLOW_API_KEY="your_api_key"
  docker compose up -d
  ```

## 配置优先级

1. 环境变量（最高优先级）
2. `.env` 文件
3. `.env.example` 中的默认值（最低优先级）

## 核心配置项说明

### 必需配置

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | `changeme` |
| `*_API_KEY` | 至少需要一个 LLM API 密钥 | `sk-xxx` |

### 重要配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MINI_LLM_ENABLED` | 启用迷你 LLM 功能 | `true` |
| `MEMORY_RETRIEVAL_TOP_K` | 检索结果数量 | `20` |
| `PROJECT__PROJECT_ISOLATION_MODE` | 项目隔离模式 | `strict` |

### 性能优化配置

| 配置项 | 说明 | 建议值 |
|--------|------|--------|
| `PERFORMANCE_CACHE_TTL_SECONDS` | 缓存过期时间 | `3600`-`7200` |
| `PERFORMANCE_MAX_CONCURRENT_REQUESTS` | 最大并发请求 | `10`-`20` |
| `MEMORY_TOKEN_BUDGET_LIMIT` | Token 预算限制 | `40000`-`60000` |

## 从旧版本迁移

如果您从包含 113 行配置的旧版本迁移：

1. 备份现有 `.env` 文件
2. 根据使用场景选择新的配置模板
3. 将必要的 API 密钥复制到新配置中
4. 其他配置项使用默认值即可

## 最佳实践

1. **开发环境**：使用 `.env.development`，所有密钥直接写入文件
2. **生产环境**：使用 `.env.production`，敏感信息通过环境变量注入
3. **密钥管理**：生产环境建议使用密钥管理服务（如 AWS Secrets Manager）
4. **配置验证**：启动前运行 `docker compose config` 验证配置

## 故障排查

### 常见问题

1. **服务无法启动**
   - 检查是否设置了必需的 API 密钥
   - 验证端口是否被占用

2. **性能问题**
   - 调整 `PERFORMANCE_*` 相关配置
   - 检查 `MEMORY_TOKEN_BUDGET_LIMIT` 是否过大

3. **跨项目隔离问题**
   - 确认 `PROJECT__PROJECT_ISOLATION_MODE` 设置正确
   - 开发环境使用 `permissive`，生产环境使用 `strict`