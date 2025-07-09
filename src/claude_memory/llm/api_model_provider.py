"""
Claude记忆管理MCP服务 - API模型提供商

支持多个API服务商的小模型调用。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import structlog
import httpx

from .mini_llm_manager import (
    ModelProviderInterface,
    MiniLLMRequest,
    MiniLLMResponse,
    TaskType,
    ModelProvider
)
from ..config.settings import get_settings
from ..utils.error_handling import handle_exceptions, ProcessingError

logger = structlog.get_logger(__name__)


class APIModelInfo:
    """API模型信息"""
    
    def __init__(
        self,
        name: str,
        api_name: str,
        provider: ModelProvider,
        context_length: int = 4096,
        capabilities: List[TaskType] = None,
        cost_per_1k_tokens: float = 0.001
    ):
        self.name = name
        self.api_name = api_name
        self.provider = provider
        self.context_length = context_length
        self.capabilities = capabilities or [
            TaskType.CLASSIFICATION,
            TaskType.SUMMARIZATION,
            TaskType.EXTRACTION,
            TaskType.COMPLETION
        ]
        self.cost_per_1k_tokens = cost_per_1k_tokens


class SiliconFlowProvider(ModelProviderInterface):
    """
    SiliconFlow API提供商
    
    支持调用SiliconFlow的各种小模型。
    """
    
    # 支持的模型
    MODELS = {
        "Qwen/Qwen2.5-0.5B-Instruct": APIModelInfo(
            name="Qwen/Qwen2.5-0.5B-Instruct",
            api_name="Qwen/Qwen2.5-0.5B-Instruct",
            provider=ModelProvider.SILICONFLOW,
            context_length=32768,
            capabilities=[TaskType.CLASSIFICATION, TaskType.EXTRACTION],
            cost_per_1k_tokens=0.0
        ),
        "Qwen/Qwen2.5-1.5B-Instruct": APIModelInfo(
            name="Qwen/Qwen2.5-1.5B-Instruct",
            api_name="Qwen/Qwen2.5-1.5B-Instruct",
            provider=ModelProvider.SILICONFLOW,
            context_length=32768,
            cost_per_1k_tokens=0.0
        ),
        "Qwen/Qwen2.5-3B-Instruct": APIModelInfo(
            name="Qwen/Qwen2.5-3B-Instruct",
            api_name="Qwen/Qwen2.5-3B-Instruct",
            provider=ModelProvider.SILICONFLOW,
            context_length=32768,
            cost_per_1k_tokens=0.0
        ),
        "Qwen/Qwen2.5-7B-Instruct": APIModelInfo(
            name="Qwen/Qwen2.5-7B-Instruct",
            api_name="Qwen/Qwen2.5-7B-Instruct",
            provider=ModelProvider.SILICONFLOW,
            context_length=32768,
            cost_per_1k_tokens=0.17 / 1000  # $0.17 per 1M tokens
        ),
        "deepseek-ai/DeepSeek-V2.5": APIModelInfo(
            name="deepseek-ai/DeepSeek-V2.5",
            api_name="deepseek-ai/DeepSeek-V2.5",
            provider=ModelProvider.SILICONFLOW,
            context_length=32768,
            cost_per_1k_tokens=0.63 / 1000  # $0.63 per 1M tokens
        )
    }
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.models.siliconflow_api_key
        self.base_url = self.settings.models.siliconflow_base_url or "https://api.siliconflow.cn/v1"
        self.client: Optional[httpx.AsyncClient] = None
        self.default_model = "deepseek-ai/DeepSeek-V2.5"
        
    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            logger.warning("SiliconFlow API key not configured")
            return
            
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        logger.info(
            "SiliconFlowProvider initialized",
            models_count=len(self.MODELS)
        )
    
    async def process(self, request: MiniLLMRequest) -> MiniLLMResponse:
        """处理请求"""
        if not self.client:
            raise ProcessingError("SiliconFlow provider not initialized")
        
        # 选择模型
        model_name = request.model_hint or self._select_model_for_task(request.task_type)
        if model_name not in self.MODELS:
            model_name = self.default_model
        
        model_info = self.MODELS[model_name]
        
        # 构建消息
        messages = self._build_messages(request)
        
        # 准备请求参数
        params = {
            "model": model_info.api_name,
            "messages": messages,
            "temperature": request.parameters.get("temperature", 0.7),
            "max_tokens": request.parameters.get("max_tokens", 512),
            "stream": False
        }
        
        # 发送请求
        start_time = asyncio.get_event_loop().time()
        
        try:
            response = await self.client.post(
                "/chat/completions",
                json=params
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 提取响应
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            # 解析输出
            output = self._parse_output(content, request.task_type)
            
            # 计算成本
            total_tokens = usage.get("total_tokens", 0)
            cost_usd = (total_tokens / 1000) * model_info.cost_per_1k_tokens
            
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return MiniLLMResponse(
                task_type=request.task_type,
                output=output,
                model_used=model_name,
                provider=ModelProvider.SILICONFLOW,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                metadata={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": total_tokens
                }
            )
            
        except httpx.HTTPError as e:
            logger.error(
                "SiliconFlow API request failed",
                model=model_name,
                error=str(e),
                status_code=getattr(e.response, "status_code", None) if hasattr(e, "response") else None
            )
            raise ProcessingError(f"SiliconFlow API request failed: {str(e)}")
    
    async def is_available(self) -> bool:
        """检查是否可用"""
        return bool(self.api_key and self.client)
    
    async def get_supported_tasks(self) -> List[TaskType]:
        """获取支持的任务类型"""
        # 收集所有模型支持的任务类型
        supported_tasks = set()
        for model_info in self.MODELS.values():
            supported_tasks.update(model_info.capabilities)
        return list(supported_tasks)
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self.client:
            await self.client.aclose()
            self.client = None
        logger.info("SiliconFlowProvider cleanup completed")
    
    def _select_model_for_task(self, task_type: TaskType) -> str:
        """为任务选择模型"""
        # 优先使用DeepSeek-V2.5处理所有任务
        # DeepSeek-V2.5在各类任务上表现优秀，且价格合理
        return "deepseek-ai/DeepSeek-V2.5"
    
    def _build_messages(self, request: MiniLLMRequest) -> List[Dict[str, str]]:
        """构建消息列表"""
        if isinstance(request.input_text, list):
            # 已经是消息格式
            return request.input_text
        
        # 根据任务类型构建系统提示
        system_message = self._get_system_message(request.task_type)
        user_message = self._get_user_message(request)
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        return messages
    
    def _get_system_message(self, task_type: TaskType) -> str:
        """获取系统消息 - 针对DeepSeek优化的中文提示词"""
        if task_type == TaskType.CLASSIFICATION:
            return """你是一个专业的文本分类专家。你的任务是准确地将输入内容分类到最合适的类别中。

要求：
1. 仔细分析文本内容的主题和语境
2. 只返回最匹配的类别名称
3. 不要添加任何解释或额外说明
4. 如果不确定，选择最接近的类别"""
        elif task_type == TaskType.SUMMARIZATION:
            return """你是一个专业的文本摘要专家。你擅长提取和凝练信息的精华。

要求：
1. 保留所有关键信息和核心观点
2. 使用简洁清晰的语言
3. 保持逻辑结构完整
4. 避免冗余和重复内容"""
        elif task_type == TaskType.EXTRACTION:
            return """你是一个专业的信息提取专家。你擅长从文本中准确识别和提取关键信息。

要求：
1. 识别并提取最重要的实体、概念或关键词
2. 保持提取信息的准确性
3. 按重要性排序
4. 避免提取无关或次要信息"""
        elif task_type == TaskType.COMPLETION:
            return """你是一名"项目记忆融合助手"（Memory Fuser）。

# 使命
- 从历史检索片段中提炼与【当前问题】直接相关的信息，并生成供 Claude Code 使用的「上下文前缀」。
- 重点突出：问题在历史中出现的时间序列、当时的修复方式及其最终状态。

# 输出结构（必须遵守）
### 背景要点（Timeline）            ← 1 行 1 事件，按时间早→晚
- [YYYY-MM-DD] <事件摘要> 【状态:<已解决/失败/未知>】

### 重要片段索引
- [1] <一句话摘要>
- [3] <一句话摘要>

### 建议注入 Prompt（直接粘贴给 Claude）
（≤ {{token_budget}} token。请优先保留与代码文件、行号、配置项相关的关键信息。）

# 约束
1. 禁止逐字复制原片段，必须用自己的话概括。
2. 若信息不足，请显式写：⚠️ 信息不足。
3. 全程使用简体中文。"""
        else:
            return "你是一个专业、友好、乐于助人的AI助手。请用清晰准确的中文回答问题。"
    
    def _get_user_message(self, request: MiniLLMRequest) -> str:
        """获取用户消息"""
        if request.task_type == TaskType.CLASSIFICATION:
            categories = request.parameters.get("categories", ["GLOBAL", "QUICK", "ARCHIVE"])
            return f"类别选项：{', '.join(categories)}\n\n内容：\n{request.input_text}\n\n请返回最合适的类别名称。"
        
        elif request.task_type == TaskType.SUMMARIZATION:
            max_length = request.parameters.get("max_length", 100)
            return f"请为以下内容生成一个不超过{max_length}字的摘要：\n\n{request.input_text}"
        
        elif request.task_type == TaskType.EXTRACTION:
            extract_type = request.parameters.get("extract_type", "keywords")
            if extract_type == "keywords":
                return f"请从以下内容中提取3-5个关键词，用逗号分隔：\n\n{request.input_text}"
            else:
                return f"请从以下内容中提取重要信息：\n\n{request.input_text}"
        
        elif request.task_type == TaskType.COMPLETION:
            # 为COMPLETION任务构建符合v3模板的用户消息
            retrieved_chunks = request.parameters.get("retrieved_chunks", request.input_text)
            user_query = request.parameters.get("user_query", "")
            token_budget = request.parameters.get("token_budget", 3000)
            project_id = request.parameters.get("project_id", "default")
            query_time = request.parameters.get("query_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            return f"""### 检索片段（Top{{top_k}}，已按相关度排序）
{retrieved_chunks}

### 当前问题
{user_query}

### 任务参数
- token_budget: {token_budget}
- project_id  : {project_id}
- start_time  : {query_time}
- 需要输出   : "概要 + 时间线 + 注入提示\""""
        
        else:
            return str(request.input_text)
    
    def _parse_output(self, response: str, task_type: TaskType) -> Any:
        """解析输出"""
        if task_type == TaskType.CLASSIFICATION:
            # 返回分类结果
            category = response.strip()
            # 移除可能的引号
            if category.startswith('"') and category.endswith('"'):
                category = category[1:-1]
            return {
                "category": category,
                "confidence": 0.95  # API模型通常有较高置信度
            }
        
        elif task_type == TaskType.EXTRACTION:
            # 解析关键词
            if "," in response:
                keywords = [k.strip() for k in response.split(",")]
            else:
                keywords = response.strip().split()
            
            return {
                "keywords": keywords[:5],  # 限制最多5个
                "entities": []
            }
        
        elif task_type == TaskType.SUMMARIZATION:
            # 返回摘要
            return response.strip()
        
        else:
            # 直接返回响应
            return response.strip()


class GeminiProvider(ModelProviderInterface):
    """
    Google Gemini API提供商
    
    支持调用Gemini的各种模型。
    """
    
    # 支持的模型
    MODELS = {
        "gemini-1.5-flash": APIModelInfo(
            name="gemini-1.5-flash",
            api_name="gemini-1.5-flash-latest",
            provider=ModelProvider.GEMINI,
            context_length=1048576,  # 1M tokens
            cost_per_1k_tokens=0.075 / 1000  # $0.075 per 1M tokens
        ),
        "gemini-1.5-flash-8b": APIModelInfo(
            name="gemini-1.5-flash-8b",
            api_name="gemini-1.5-flash-8b-latest",
            provider=ModelProvider.GEMINI,
            context_length=1048576,
            cost_per_1k_tokens=0.0375 / 1000  # $0.0375 per 1M tokens
        )
    }
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.models.gemini_api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.client: Optional[httpx.AsyncClient] = None
        self.default_model = "gemini-1.5-flash-8b"
        
    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            logger.warning("Gemini API key not configured")
            return
            
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            params={"key": self.api_key},
            timeout=30.0
        )
        
        logger.info(
            "GeminiProvider initialized",
            models_count=len(self.MODELS)
        )
    
    async def process(self, request: MiniLLMRequest) -> MiniLLMResponse:
        """处理请求"""
        if not self.client:
            raise ProcessingError("Gemini provider not initialized")
        
        # 选择模型
        model_name = request.model_hint or self.default_model
        if model_name not in self.MODELS:
            model_name = self.default_model
        
        model_info = self.MODELS[model_name]
        
        # 构建请求内容
        content = self._build_content(request)
        
        # 准备请求参数
        params = {
            "contents": [{"parts": [{"text": content}]}],
            "generationConfig": {
                "temperature": request.parameters.get("temperature", 0.7),
                "maxOutputTokens": request.parameters.get("max_tokens", 512),
                "topP": request.parameters.get("top_p", 0.95)
            }
        }
        
        # 发送请求
        start_time = asyncio.get_event_loop().time()
        
        try:
            response = await self.client.post(
                f"/models/{model_info.api_name}:generateContent",
                json=params
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 提取响应
            candidates = data.get("candidates", [])
            if not candidates:
                raise ProcessingError("No response from Gemini")
            
            content = candidates[0]["content"]["parts"][0]["text"]
            
            # 解析输出
            output = self._parse_output(content, request.task_type)
            
            # 估算token使用（Gemini API不直接返回token数）
            estimated_tokens = len(content) // 4  # 粗略估算
            cost_usd = (estimated_tokens / 1000) * model_info.cost_per_1k_tokens
            
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return MiniLLMResponse(
                task_type=request.task_type,
                output=output,
                model_used=model_name,
                provider=ModelProvider.GEMINI,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                metadata={
                    "estimated_tokens": estimated_tokens
                }
            )
            
        except httpx.HTTPError as e:
            logger.error(
                "Gemini API request failed",
                model=model_name,
                error=str(e)
            )
            raise ProcessingError(f"Gemini API request failed: {str(e)}")
    
    async def is_available(self) -> bool:
        """检查是否可用"""
        return bool(self.api_key and self.client)
    
    async def get_supported_tasks(self) -> List[TaskType]:
        """获取支持的任务类型"""
        # Gemini支持所有任务类型
        return list(TaskType)
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self.client:
            await self.client.aclose()
            self.client = None
        logger.info("GeminiProvider cleanup completed")
    
    def _build_content(self, request: MiniLLMRequest) -> str:
        """构建请求内容"""
        if isinstance(request.input_text, list):
            # 转换消息格式为文本
            content = ""
            for msg in request.input_text:
                role = msg.get("role", "user")
                text = msg.get("content", "")
                if role == "system":
                    content += f"Instructions: {text}\n\n"
                elif role == "user":
                    content += f"User: {text}\n\n"
                elif role == "assistant":
                    content += f"Assistant: {text}\n\n"
            content += "Assistant: "
            return content
        
        # 根据任务类型构建提示
        if request.task_type == TaskType.CLASSIFICATION:
            categories = request.parameters.get("categories", ["GLOBAL", "QUICK", "ARCHIVE"])
            return f"""Classify the following content into one of these categories: {', '.join(categories)}

Content:
{request.input_text}

Return only the category name, nothing else.

Category:"""
        
        elif request.task_type == TaskType.SUMMARIZATION:
            max_length = request.parameters.get("max_length", 100)
            return f"""Generate a concise summary (max {max_length} words) of the following content:

{request.input_text}

Summary:"""
        
        elif request.task_type == TaskType.EXTRACTION:
            extract_type = request.parameters.get("extract_type", "keywords")
            if extract_type == "keywords":
                return f"""Extract 3-5 keywords from the following content (comma-separated):

{request.input_text}

Keywords:"""
            else:
                return f"""Extract important information from the following content:

{request.input_text}

Important information:"""
        
        elif request.task_type == TaskType.COMPLETION:
            # 为COMPLETION任务构建符合v3模板的内容
            retrieved_chunks = request.parameters.get("retrieved_chunks", request.input_text)
            user_query = request.parameters.get("user_query", "")
            token_budget = request.parameters.get("token_budget", 3000)
            project_id = request.parameters.get("project_id", "default")
            query_time = request.parameters.get("query_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            # 构建完整的v3模板内容
            return f"""Instructions: 你是一名"项目记忆融合助手"（Memory Fuser）。

# 使命
- 从历史检索片段中提炼与【当前问题】直接相关的信息，并生成供 Claude Code 使用的「上下文前缀」。
- 重点突出：问题在历史中出现的时间序列、当时的修复方式及其最终状态。

# 输出结构（必须遵守）
### 背景要点（Timeline）            ← 1 行 1 事件，按时间早→晚
- [YYYY-MM-DD] <事件摘要> 【状态:<已解决/失败/未知>】

### 重要片段索引
- [1] <一句话摘要>
- [3] <一句话摘要>

### 建议注入 Prompt（直接粘贴给 Claude）
（≤ {token_budget} token。请优先保留与代码文件、行号、配置项相关的关键信息。）

# 约束
1. 禁止逐字复制原片段，必须用自己的话概括。
2. 若信息不足，请显式写：⚠️ 信息不足。
3. 全程使用简体中文。

User: ### 检索片段（Top{{top_k}}，已按相关度排序）
{retrieved_chunks}

### 当前问题
{user_query}

### 任务参数
- token_budget: {token_budget}
- project_id  : {project_id}
- start_time  : {query_time}
- 需要输出   : "概要 + 时间线 + 注入提示\"
    
    def _parse_output(self, response: str, task_type: TaskType) -> Any:
        """解析输出"""
        # 与SiliconFlow提供商相同的解析逻辑
        if task_type == TaskType.CLASSIFICATION:
            category = response.strip()
            if category.startswith('"') and category.endswith('"'):
                category = category[1:-1]
            return {
                "category": category,
                "confidence": 0.95
            }
        
        elif task_type == TaskType.EXTRACTION:
            if "," in response:
                keywords = [k.strip() for k in response.split(",")]
            else:
                keywords = response.strip().split()
            
            return {
                "keywords": keywords[:5],
                "entities": []
            }
        
        elif task_type == TaskType.SUMMARIZATION:
            return response.strip()
        
        else:
            return response.strip()


class OpenRouterProvider(ModelProviderInterface):
    """
    OpenRouter API提供商
    
    支持调用OpenRouter上的各种模型。
    """
    
    # 支持的模型
    MODELS = {
        "deepseek/deepseek-chat-v3-0324:free": APIModelInfo(
            name="deepseek/deepseek-chat-v3-0324:free",
            api_name="deepseek/deepseek-chat-v3-0324:free",
            provider=ModelProvider.OPENROUTER,
            context_length=64000,
            cost_per_1k_tokens=0.0  # 免费模型
        ),
        "mistralai/mistral-7b-instruct": APIModelInfo(
            name="mistralai/mistral-7b-instruct",
            api_name="mistralai/mistral-7b-instruct",
            provider=ModelProvider.OPENROUTER,
            context_length=32768,
            cost_per_1k_tokens=0.07 / 1000  # $0.07 per 1M tokens
        ),
        "google/gemma-2-9b-it": APIModelInfo(
            name="google/gemma-2-9b-it",
            api_name="google/gemma-2-9b-it",
            provider=ModelProvider.OPENROUTER,
            context_length=8192,
            cost_per_1k_tokens=0.20 / 1000  # $0.20 per 1M tokens
        ),
        "meta-llama/llama-3.2-3b-instruct": APIModelInfo(
            name="meta-llama/llama-3.2-3b-instruct",
            api_name="meta-llama/llama-3.2-3b-instruct",
            provider=ModelProvider.OPENROUTER,
            context_length=128000,
            cost_per_1k_tokens=0.06 / 1000  # $0.06 per 1M tokens
        )
    }
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.models.openrouter_api_key
        self.base_url = self.settings.models.openrouter_base_url or "https://openrouter.ai/api/v1"
        self.client: Optional[httpx.AsyncClient] = None
        self.default_model = "deepseek/deepseek-chat-v3-0324:free"  # 默认使用免费的DeepSeek
        
    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            logger.warning("OpenRouter API key not configured")
            return
            
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/claude-memory-mcp",
                "X-Title": "Claude Memory MCP Service"
            },
            timeout=30.0
        )
        
        logger.info(
            "OpenRouterProvider initialized",
            models_count=len(self.MODELS)
        )
    
    async def process(self, request: MiniLLMRequest) -> MiniLLMResponse:
        """处理请求"""
        if not self.client:
            raise ProcessingError("OpenRouter provider not initialized")
        
        # 选择模型
        model_name = request.model_hint or self.default_model
        if model_name not in self.MODELS:
            model_name = self.default_model
        
        model_info = self.MODELS[model_name]
        
        # 构建消息
        messages = self._build_messages(request)
        
        # 准备请求参数
        params = {
            "model": model_info.api_name,
            "messages": messages,
            "temperature": request.parameters.get("temperature", 0.7),
            "max_tokens": request.parameters.get("max_tokens", 512),
            "stream": False
        }
        
        # 发送请求
        start_time = asyncio.get_event_loop().time()
        
        try:
            response = await self.client.post(
                "/chat/completions",
                json=params
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 提取响应
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            # 解析输出
            output = self._parse_output(content, request.task_type)
            
            # 计算成本
            total_tokens = usage.get("total_tokens", 0)
            cost_usd = (total_tokens / 1000) * model_info.cost_per_1k_tokens
            
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return MiniLLMResponse(
                task_type=request.task_type,
                output=output,
                model_used=model_name,
                provider=ModelProvider.OPENROUTER,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                metadata={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": total_tokens
                }
            )
            
        except httpx.HTTPError as e:
            logger.error(
                "OpenRouter API request failed",
                model=model_name,
                error=str(e)
            )
            raise ProcessingError(f"OpenRouter API request failed: {str(e)}")
    
    async def is_available(self) -> bool:
        """检查是否可用"""
        return bool(self.api_key and self.client)
    
    async def get_supported_tasks(self) -> List[TaskType]:
        """获取支持的任务类型"""
        # OpenRouter支持所有任务类型
        return list(TaskType)
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self.client:
            await self.client.aclose()
            self.client = None
        logger.info("OpenRouterProvider cleanup completed")
    
    def _build_messages(self, request: MiniLLMRequest) -> List[Dict[str, str]]:
        """构建消息列表"""
        # 与SiliconFlow提供商相同的逻辑
        if isinstance(request.input_text, list):
            return request.input_text
        
        system_message = self._get_system_message(request.task_type)
        user_message = self._get_user_message(request)
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        return messages
    
    def _get_system_message(self, task_type: TaskType) -> str:
        """获取系统消息"""
        # 与SiliconFlow提供商相同的逻辑
        if task_type == TaskType.CLASSIFICATION:
            return "You are a text classification assistant. Based on the provided categories, classify the content into the most appropriate category. Return only the category name."
        elif task_type == TaskType.SUMMARIZATION:
            return "You are a text summarization assistant. Generate concise and accurate summaries that preserve key information."
        elif task_type == TaskType.EXTRACTION:
            return "You are an information extraction assistant. Extract key information, entities, or keywords from the text."
        elif task_type == TaskType.COMPLETION:
            # 使用与SiliconFlow相同的中文提示词（DeepSeek模型支持中文）
            return """你是一名"项目记忆融合助手"（Memory Fuser）。

# 使命
- 从历史检索片段中提炼与【当前问题】直接相关的信息，并生成供 Claude Code 使用的「上下文前缀」。
- 重点突出：问题在历史中出现的时间序列、当时的修复方式及其最终状态。

# 输出结构（必须遵守）
### 背景要点（Timeline）            ← 1 行 1 事件，按时间早→晚
- [YYYY-MM-DD] <事件摘要> 【状态:<已解决/失败/未知>】

### 重要片段索引
- [1] <一句话摘要>
- [3] <一句话摘要>

### 建议注入 Prompt（直接粘贴给 Claude）
（≤ {{token_budget}} token。请优先保留与代码文件、行号、配置项相关的关键信息。）

# 约束
1. 禁止逐字复制原片段，必须用自己的话概括。
2. 若信息不足，请显式写：⚠️ 信息不足。
3. 全程使用简体中文。"""
        else:
            return "You are a helpful AI assistant."
    
    def _get_user_message(self, request: MiniLLMRequest) -> str:
        """获取用户消息"""
        # 与SiliconFlow提供商相同的逻辑
        if request.task_type == TaskType.CLASSIFICATION:
            categories = request.parameters.get("categories", ["GLOBAL", "QUICK", "ARCHIVE"])
            return f"Categories: {', '.join(categories)}\n\nContent:\n{request.input_text}\n\nReturn the most appropriate category name."
        
        elif request.task_type == TaskType.SUMMARIZATION:
            max_length = request.parameters.get("max_length", 100)
            return f"Generate a summary (max {max_length} words) of:\n\n{request.input_text}"
        
        elif request.task_type == TaskType.EXTRACTION:
            extract_type = request.parameters.get("extract_type", "keywords")
            if extract_type == "keywords":
                return f"Extract 3-5 keywords from the following content (comma-separated):\n\n{request.input_text}"
            else:
                return f"Extract important information from:\n\n{request.input_text}"
        
        elif request.task_type == TaskType.COMPLETION:
            # 为COMPLETION任务构建符合v3模板的用户消息
            retrieved_chunks = request.parameters.get("retrieved_chunks", request.input_text)
            user_query = request.parameters.get("user_query", "")
            token_budget = request.parameters.get("token_budget", 3000)
            project_id = request.parameters.get("project_id", "default")
            query_time = request.parameters.get("query_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            return f"""### 检索片段（Top{{top_k}}，已按相关度排序）
{retrieved_chunks}

### 当前问题
{user_query}

### 任务参数
- token_budget: {token_budget}
- project_id  : {project_id}
- start_time  : {query_time}
- 需要输出   : "概要 + 时间线 + 注入提示\""""
        
        else:
            return str(request.input_text)
    
    def _parse_output(self, response: str, task_type: TaskType) -> Any:
        """解析输出"""
        # 与其他提供商相同的解析逻辑
        if task_type == TaskType.CLASSIFICATION:
            category = response.strip()
            if category.startswith('"') and category.endswith('"'):
                category = category[1:-1]
            return {
                "category": category,
                "confidence": 0.95
            }
        
        elif task_type == TaskType.EXTRACTION:
            if "," in response:
                keywords = [k.strip() for k in response.split(",")]
            else:
                keywords = response.strip().split()
            
            return {
                "keywords": keywords[:5],
                "entities": []
            }
        
        elif task_type == TaskType.SUMMARIZATION:
            return response.strip()
        
        else:
            return response.strip()