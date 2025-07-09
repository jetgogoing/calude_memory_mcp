#!/usr/bin/env python3
"""
Claude Memory HTTP API Server
提供 HTTP 接口访问 MCP 功能
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from claude_memory.managers.service_manager import ServiceManager
from claude_memory.config.settings import Settings


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局服务管理器
service_manager = None
settings = Settings()


class MemoryStoreRequest(BaseModel):
    """存储记忆请求"""
    content: str
    project_id: str = "default"
    metadata: Dict[str, Any] = {}


class MemorySearchRequest(BaseModel):
    """搜索记忆请求"""
    query: str
    project_id: str = "default"
    limit: int = 5
    min_score: float = 0.3


class ConversationRequest(BaseModel):
    """对话请求"""
    messages: list
    project_id: str = "default"
    title: str = None


class MemoryInjectRequest(BaseModel):
    """记忆注入请求"""
    original_prompt: str
    query_text: Optional[str] = None
    context_hint: Optional[str] = None
    injection_mode: str = "balanced"
    max_tokens: int = 2000
    project_id: str = "default"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global service_manager
    
    logger.info("Starting Claude Memory API Server...")
    
    # 初始化服务管理器
    service_manager = ServiceManager()
    await service_manager.start_service()
    
    logger.info("API Server started successfully")
    
    yield
    
    # 清理
    logger.info("Shutting down API Server...")
    await service_manager.stop_service()


# 创建 FastAPI 应用
app = FastAPI(
    title="Claude Memory API",
    description="HTTP API for Claude Memory MCP Service",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "claude-memory-api",
        "version": "1.0.0"
    }


@app.post("/memory/store")
async def store_memory(request: MemoryStoreRequest):
    """存储记忆"""
    try:
        from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType
        
        # 创建消息
        message = MessageModel(
            conversation_id="",  # 会在创建对话时设置
            message_type=MessageType.HUMAN,
            content=request.content,
            token_count=len(request.content.split()) * 1  # 简单估算
        )
        
        # 创建对话
        conversation = ConversationModel(
            project_id=request.project_id,
            title=f"Memory: {request.content[:50]}...",
            messages=[message],
            message_count=1,
            token_count=message.token_count,
            metadata=request.metadata
        )
        
        # 更新消息的conversation_id
        message.conversation_id = conversation.id
        
        # 处理对话（压缩并存储）
        await service_manager._handle_new_conversation(conversation)
        
        return {
            "success": True,
            "conversation_id": conversation.id,
            "project_id": conversation.project_id,
            "message": "Memory stored successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to store memory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/search")
async def search_memory(request: MemorySearchRequest):
    """搜索记忆"""
    try:
        from claude_memory.models.data_models import SearchQuery
        
        # 创建搜索查询
        search_query = SearchQuery(
            query=request.query,
            query_type="hybrid",
            limit=request.limit,
            min_score=request.min_score  # 使用请求中的评分阈值
        )
        
        # 调用ServiceManager的搜索方法（全局共享记忆）
        response = await service_manager.search_memories(search_query)
        
        return {
            "success": True,
            "query": request.query,
            "results": [
                {
                    "content": result.memory_unit.content,
                    "title": result.memory_unit.title,
                    "summary": result.memory_unit.summary,
                    "score": result.relevance_score,
                    "keywords": result.memory_unit.keywords,
                    "created_at": result.memory_unit.created_at.isoformat()
                }
                for result in response.results
            ],
            "count": len(response.results),
            "search_time_ms": response.search_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to search memory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversation/store")
async def store_conversation(request: ConversationRequest):
    """存储整个对话"""
    try:
        from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType
        
        # 创建消息列表
        messages = []
        total_tokens = 0
        for msg in request.messages:
            # 确定消息类型
            msg_type = MessageType.HUMAN if msg.get("role") == "user" else MessageType.ASSISTANT
            if msg.get("role") == "system":
                msg_type = MessageType.SYSTEM
                
            message = MessageModel(
                conversation_id="",  # 会在创建对话时设置
                message_type=msg_type,
                content=msg.get("content", ""),
                token_count=len(msg.get("content", "").split()) * 1  # 简单估算
            )
            messages.append(message)
            total_tokens += message.token_count
        
        # 创建对话
        conversation = ConversationModel(
            project_id=request.project_id,
            title=request.title or "Untitled Conversation",
            messages=messages,
            message_count=len(messages),
            token_count=total_tokens
        )
        
        # 更新所有消息的conversation_id
        for msg in messages:
            msg.conversation_id = conversation.id
        
        # 处理对话（压缩并存储）
        await service_manager._handle_new_conversation(conversation)
        
        return {
            "success": True,
            "conversation_id": conversation.id,
            "project_id": conversation.project_id,
            "message": "Conversation stored successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to store conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects")
async def list_projects():
    """列出所有项目"""
    try:
        # ProjectManager使用同步方法
        loop = asyncio.get_event_loop()
        projects = await loop.run_in_executor(
            None, service_manager.project_manager.list_projects
        )
        return {
            "success": True,
            "projects": [
                {
                    "project_id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "created_at": p.created_at.isoformat()
                }
                for p in projects
            ],
            "count": len(projects)
        }
    except Exception as e:
        logger.error(f"Failed to list projects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/projects")
async def create_project(project_id: str, name: str = None, description: str = None):
    """创建新项目"""
    try:
        # ProjectManager使用同步方法
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(
            None,
            service_manager.project_manager.create_project,
            project_id,
            name or project_id,
            description
        )
        
        return {
            "success": True,
            "project": {
                "project_id": project.id,
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at.isoformat()
            },
            "message": "Project created successfully"
        }
    except Exception as e:
        logger.error(f"Failed to create project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/inject")
async def inject_memory(request: MemoryInjectRequest):
    """注入记忆到提示词"""
    try:
        from claude_memory.models.data_models import ContextInjectionRequest
        
        # 创建注入请求
        injection_req = ContextInjectionRequest(
            original_prompt=request.original_prompt,
            query_text=request.query_text or request.original_prompt,
            context_hint=request.context_hint,
            injection_mode=request.injection_mode,
            max_tokens=request.max_tokens
        )
        
        # TODO: 需要在内部处理project_id过滤
        # 目前先调用ServiceManager的注入方法
        response = await service_manager.inject_context(injection_req)
        
        return {
            "success": True,
            "enhanced_prompt": response.enhanced_prompt,
            "injected_memories": [
                {
                    "id": mem.id,
                    "title": mem.title,
                    "content": mem.content,
                    "summary": mem.summary,
                    "type": mem.unit_type.value,
                    "token_count": mem.token_count
                }
                for mem in response.injected_memories
            ],
            "tokens_used": response.tokens_used,
            "processing_time_ms": response.processing_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to inject memory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "claude_memory.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )