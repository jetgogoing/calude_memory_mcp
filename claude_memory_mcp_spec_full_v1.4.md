
# Claude 记忆管理 MCP 服务 — 完整说明书（v1.4 架构更新）  
版本：v1.4  
作者：Jet  
更新日期：2025-07-06  

---

## 📘 架构总览（v1.4）

在 v1.4 架构中，我们正式采用以下新策略：

- ❌ 不再使用 Quick-MU / Fast-MU 分级结构，全部记忆统一以原文嵌入向量数据库
- ✅ 采用 Qwen3-Embedding-8B 与 Qwen3-Reranker-8B 固定作为检索主力（调用 siliconflow API）
- ✅ 在所有检索流程中，加入 MemoryFuser 阶段，使用 Gemini 2.5 Flash 模型拼接成高质量提示词
- ✅ 强调 PromptBuilder 的作用仅限于结构整理与 token 截断，不再做摘要
- ✅ 全局默认启用拼接模型注入（由 GEMINI_API_KEY 调用）

---

## 📐 完整流程图（v1.4 核心结构）

```mermaid
flowchart TD
    Q[Claude CLI 用户提问] --> V[Qwen3-Embedding 查询向量]
    V --> R[向量数据库 Top-20 检索]
    R --> F[Reranker 精排 Top-5 (Qwen3-Reranker)]
    F --> M[MemoryFuser (Gemini 2.5 Flash 拼接注入)]
    M --> B[PromptBuilder + TokenLimiter]
    B --> C[Claude 接收上下文处理]
```

---

## 🔧 模块角色定义（v1.4）

### 🧱 MemoryFuser 模块（新增）

| 项目 | 内容 |
|------|------|
| 名称 | `memory_fuser.py` |
| 输入 | 当前 Query + Rerank Top-N 原文片段 |
| 输出 | 结构化 Prompt 注入 Claude |
| 模型 | `gemini-2.5-flash`（默认） |
| 提示词模板 | `prompts/memory_fusion_prompt_programming.txt` |
| 调用 API | `GEMINI_API_KEY` |
| 描述 | 用 LLM 将片段拼接成结构明确、压缩有序、可直接注入 Claude 的 prompt 上下文 |

---

### 📍 PromptBuilder 模块（简化）

**作用**：将 MemoryFuser 返回的摘要或结构化提示词注入 Claude，对剩余部分进行 token 管控与包裹。

- 不再拼接片段，仅处理 TokenLimiter 截断逻辑
- 添加系统注释与包装引导词，如：

```
以下是与你当前任务相关的项目背景与历史信息，请优先理解再继续操作：
```

---

### 📍 TokenLimiter 模块

**作用**：对 MemoryFuser 输出 + 系统提示进行 Token 限制控制

- 默认总预算：`20000 tokens`
- 对 MemoryFuser 输出不截断，仅压缩其他 Prompt 组件
- 如超限：尝试剔除辅助注释或历史问答引用

---

## ⚙️ 检索配置建议（固定 Qwen3 模型）

```yaml
RETRIEVAL_TOP_K: 20
RERANK_TOP_K: 5
SIMILARITY_THRESHOLD: 0.7
HYBRID_SEARCH_ALPHA: 0.0   # 完全语义检索

EMBEDDING_MODEL: "Qwen3-Embedding-8B@siliconflow"
RERANK_MODEL: "Qwen3-Reranker-8B@siliconflow"
```

---

## 📎 模板配置建议（memory_fuser_config.yaml）

```yaml
enabled: true
model: gemini-2.5-flash
temperature: 0.2
prompt_template: ./prompts/memory_fusion_prompt_programming.txt
token_limit: 800
language: zh
```

---

## 🆕 版本更新摘要（v1.4 相较 v1.3）

| 变更项 | 描述 |
|--------|------|
| ✅ 全时启用拼接模型 | MemoryFuser 模块始终在召回后运行 |
| ✅ 移除 Quick-MU 等多层级结构 | 全部统一原文向量嵌入 |
| ✅ Qwen3 模型锁定 | 固定使用 siliconflow 提供的 Qwen3 系列 |
| ✅ PromptBuilder 精简化 | 不再执行拼接逻辑，仅保留包裹与 token 控制 |
| ✅ 成本更明确 | 只使用 Gemini Flash + Qwen Embedding/Reranker

---
