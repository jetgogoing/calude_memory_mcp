"""
Claude记忆管理MCP服务 - 本地模型提供商

使用 llama-cpp-python 运行本地小模型。
"""

from __future__ import annotations

import asyncio
import os
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import urlretrieve

import structlog

# 可选导入llama-cpp-python
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    Llama = None  # 占位符

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


class ModelInfo:
    """模型信息"""
    
    def __init__(
        self,
        name: str,
        filename: str,
        url: str,
        size_mb: int,
        context_length: int = 2048,
        capabilities: List[TaskType] = None
    ):
        self.name = name
        self.filename = filename
        self.url = url
        self.size_mb = size_mb
        self.context_length = context_length
        self.capabilities = capabilities or [
            TaskType.CLASSIFICATION,
            TaskType.SUMMARIZATION,
            TaskType.EXTRACTION,
            TaskType.COMPLETION
        ]


# 支持的本地模型列表
SUPPORTED_MODELS = {
    "qwen2.5-0.5b-instruct": ModelInfo(
        name="qwen2.5-0.5b-instruct",
        filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
        url="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        size_mb=400,
        context_length=2048,
        capabilities=[TaskType.CLASSIFICATION, TaskType.EXTRACTION]
    ),
    "qwen2.5-1.5b-instruct": ModelInfo(
        name="qwen2.5-1.5b-instruct",
        filename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        url="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        size_mb=1100,
        context_length=4096,
        capabilities=[
            TaskType.CLASSIFICATION,
            TaskType.SUMMARIZATION,
            TaskType.EXTRACTION,
            TaskType.COMPLETION
        ]
    ),
    "phi-3-mini": ModelInfo(
        name="phi-3-mini",
        filename="phi-3-mini-4k-instruct-q4.gguf",
        url="https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf",
        size_mb=2400,
        context_length=4096
    ),
    "tinyllama-1.1b": ModelInfo(
        name="tinyllama-1.1b",
        filename="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        url="https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        size_mb=700,
        context_length=2048
    )
}


class LocalModelProvider(ModelProviderInterface):
    """
    本地模型提供商
    
    使用 llama-cpp-python 加载和运行 GGUF 格式的模型。
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.models_dir = Path(self.settings.mini_llm.models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.loaded_models: Dict[str, Llama] = {}
        self.model_info = SUPPORTED_MODELS
        self.max_memory_gb = self.settings.mini_llm.max_memory_gb
        self.current_memory_usage = 0.0
        
    async def initialize(self) -> None:
        """初始化提供商"""
        if not LLAMA_CPP_AVAILABLE:
            logger.warning(
                "llama-cpp-python not available, local models disabled. "
                "Install with: pip install llama-cpp-python"
            )
            return
            
        logger.info(
            "Initializing LocalModelProvider",
            models_dir=str(self.models_dir),
            max_memory_gb=self.max_memory_gb
        )
        
        # 检查已下载的模型
        available_models = self._check_available_models()
        logger.info(
            "Available local models",
            count=len(available_models),
            models=list(available_models.keys())
        )
        
        # 预加载默认模型
        default_model = self.settings.mini_llm.default_model
        if default_model and default_model in available_models:
            await self._load_model(default_model)
    
    async def process(self, request: MiniLLMRequest) -> MiniLLMResponse:
        """处理请求"""
        if not LLAMA_CPP_AVAILABLE:
            raise ProcessingError("llama-cpp-python not available")
            
        # 获取模型名称
        model_name = request.model_hint or self._select_model_for_task(request.task_type)
        
        if not model_name:
            raise ProcessingError(f"No suitable model for task: {request.task_type}")
        
        # 确保模型已加载
        model = await self._ensure_model_loaded(model_name)
        
        # 构建提示词
        prompt = self._build_prompt(request)
        
        # 生成响应
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 在线程池中运行以避免阻塞
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._generate_response,
                model,
                prompt,
                request.parameters
            )
            
            # 解析输出
            output = self._parse_output(response, request.task_type)
            
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return MiniLLMResponse(
                task_type=request.task_type,
                output=output,
                model_used=model_name,
                provider=ModelProvider.LOCAL,
                latency_ms=latency_ms,
                cost_usd=0.0,  # 本地模型无成本
                metadata={
                    "prompt_length": len(prompt),
                    "response_length": len(response),
                    "model_path": str(self.models_dir / self.model_info[model_name].filename)
                }
            )
            
        except Exception as e:
            logger.error(
                "Local model generation failed",
                model=model_name,
                error=str(e)
            )
            raise ProcessingError(f"Local model generation failed: {str(e)}")
    
    async def is_available(self) -> bool:
        """检查是否可用"""
        if not LLAMA_CPP_AVAILABLE:
            return False
            
        try:
            # 检查是否有可用的模型
            available_models = self._check_available_models()
            return len(available_models) > 0
        except Exception:
            return False
    
    async def get_supported_tasks(self) -> List[TaskType]:
        """获取支持的任务类型"""
        # 收集所有已下载模型支持的任务类型
        supported_tasks = set()
        available_models = self._check_available_models()
        
        for model_name in available_models:
            if model_name in self.model_info:
                supported_tasks.update(self.model_info[model_name].capabilities)
        
        return list(supported_tasks)
    
    async def cleanup(self) -> None:
        """清理资源"""
        logger.info("Cleaning up LocalModelProvider...")
        
        # 卸载所有模型
        for model_name in list(self.loaded_models.keys()):
            self._unload_model(model_name)
        
        logger.info("LocalModelProvider cleanup completed")
    
    def _check_available_models(self) -> Dict[str, Path]:
        """检查已下载的模型"""
        available = {}
        
        for model_name, info in self.model_info.items():
            model_path = self.models_dir / info.filename
            if model_path.exists():
                available[model_name] = model_path
        
        return available
    
    async def _ensure_model_loaded(self, model_name: str) -> Llama:
        """确保模型已加载"""
        if model_name in self.loaded_models:
            return self.loaded_models[model_name]
        
        # 检查模型是否已下载
        available_models = self._check_available_models()
        if model_name not in available_models:
            # 下载模型
            await self._download_model(model_name)
        
        # 加载模型
        return await self._load_model(model_name)
    
    async def _download_model(self, model_name: str) -> None:
        """下载模型"""
        if model_name not in self.model_info:
            raise ProcessingError(f"Unknown model: {model_name}")
        
        info = self.model_info[model_name]
        model_path = self.models_dir / info.filename
        
        logger.info(
            "Downloading model",
            model=model_name,
            url=info.url,
            size_mb=info.size_mb
        )
        
        # 使用异步下载
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            urlretrieve,
            info.url,
            str(model_path)
        )
        
        logger.info(
            "Model downloaded",
            model=model_name,
            path=str(model_path)
        )
    
    async def _load_model(self, model_name: str) -> Llama:
        """加载模型"""
        if model_name in self.loaded_models:
            return self.loaded_models[model_name]
        
        info = self.model_info[model_name]
        model_path = self.models_dir / info.filename
        
        # 检查内存限制
        model_size_gb = info.size_mb / 1024
        if self.current_memory_usage + model_size_gb > self.max_memory_gb:
            # 需要卸载一些模型
            await self._free_memory(model_size_gb)
        
        logger.info(
            "Loading model",
            model=model_name,
            path=str(model_path),
            context_length=info.context_length
        )
        
        # 在线程池中加载模型
        loop = asyncio.get_event_loop()
        model = await loop.run_in_executor(
            None,
            Llama,
            str(model_path),
            info.context_length,  # n_ctx
            512,  # n_batch
            1,    # n_threads
            True  # use_mmap
        )
        
        self.loaded_models[model_name] = model
        self.current_memory_usage += model_size_gb
        
        logger.info(
            "Model loaded",
            model=model_name,
            memory_usage_gb=self.current_memory_usage
        )
        
        return model
    
    def _unload_model(self, model_name: str) -> None:
        """卸载模型"""
        if model_name not in self.loaded_models:
            return
        
        del self.loaded_models[model_name]
        
        info = self.model_info[model_name]
        self.current_memory_usage -= info.size_mb / 1024
        
        logger.info(
            "Model unloaded",
            model=model_name,
            memory_usage_gb=self.current_memory_usage
        )
    
    async def _free_memory(self, required_gb: float) -> None:
        """释放内存"""
        # 简单策略：卸载最早加载的模型
        while self.current_memory_usage + required_gb > self.max_memory_gb:
            if not self.loaded_models:
                raise ProcessingError("Cannot free enough memory for model")
            
            # 卸载第一个模型
            model_name = next(iter(self.loaded_models))
            self._unload_model(model_name)
    
    def _select_model_for_task(self, task_type: TaskType) -> Optional[str]:
        """为任务选择模型"""
        available_models = self._check_available_models()
        
        # 找到支持该任务的最小模型
        suitable_models = []
        for model_name in available_models:
            if model_name in self.model_info:
                info = self.model_info[model_name]
                if task_type in info.capabilities:
                    suitable_models.append((model_name, info.size_mb))
        
        if suitable_models:
            # 选择最小的模型
            suitable_models.sort(key=lambda x: x[1])
            return suitable_models[0][0]
        
        return None
    
    def _build_prompt(self, request: MiniLLMRequest) -> str:
        """构建提示词"""
        if request.task_type == TaskType.CLASSIFICATION:
            return self._build_classification_prompt(request)
        elif request.task_type == TaskType.SUMMARIZATION:
            return self._build_summarization_prompt(request)
        elif request.task_type == TaskType.EXTRACTION:
            return self._build_extraction_prompt(request)
        else:
            return self._build_completion_prompt(request)
    
    def _build_classification_prompt(self, request: MiniLLMRequest) -> str:
        """构建分类提示词"""
        categories = request.parameters.get("categories", ["GLOBAL", "QUICK", "ARCHIVE"])
        
        prompt = f"""请将以下内容分类到合适的类别中。

类别选项：{', '.join(categories)}

内容：
{request.input_text}

请直接返回类别名称，不要有其他说明。

类别："""
        
        return prompt
    
    def _build_summarization_prompt(self, request: MiniLLMRequest) -> str:
        """构建摘要提示词"""
        max_length = request.parameters.get("max_length", 100)
        
        prompt = f"""请为以下内容生成一个简洁的摘要（不超过{max_length}字）：

内容：
{request.input_text}

摘要："""
        
        return prompt
    
    def _build_extraction_prompt(self, request: MiniLLMRequest) -> str:
        """构建信息提取提示词"""
        extract_type = request.parameters.get("extract_type", "keywords")
        
        if extract_type == "keywords":
            prompt = f"""请从以下内容中提取3-5个关键词：

内容：
{request.input_text}

关键词（用逗号分隔）："""
        else:
            prompt = f"""请从以下内容中提取重要信息：

内容：
{request.input_text}

重要信息："""
        
        return prompt
    
    def _build_completion_prompt(self, request: MiniLLMRequest) -> str:
        """构建通用补全提示词"""
        if isinstance(request.input_text, list):
            # 对话格式
            messages = request.input_text
            prompt = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt += f"系统：{content}\n"
                elif role == "user":
                    prompt += f"用户：{content}\n"
                elif role == "assistant":
                    prompt += f"助手：{content}\n"
            prompt += "助手："
        else:
            prompt = request.input_text
        
        return prompt
    
    def _generate_response(
        self,
        model: Llama,
        prompt: str,
        parameters: Dict[str, Any]
    ) -> str:
        """生成响应"""
        # 提取参数
        max_tokens = parameters.get("max_tokens", 512)
        temperature = parameters.get("temperature", 0.7)
        top_p = parameters.get("top_p", 0.9)
        
        # 生成
        response = model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            echo=False
        )
        
        return response["choices"][0]["text"].strip()
    
    def _parse_output(self, response: str, task_type: TaskType) -> Any:
        """解析输出"""
        if task_type == TaskType.CLASSIFICATION:
            # 返回分类结果
            return {
                "category": response.strip(),
                "confidence": 0.9  # 简化处理
            }
        elif task_type == TaskType.EXTRACTION:
            # 解析关键词
            keywords = [k.strip() for k in response.split(",")]
            return {
                "keywords": keywords,
                "entities": []  # 简化处理
            }
        else:
            # 直接返回文本
            return response