"""
Claude记忆管理MCP服务 - 数据模型定义

定义系统中使用的所有核心数据模型。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Boolean,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# SQLAlchemy Base
Base = declarative_base()


# 枚举类型
class MessageType(str, Enum):
    """消息类型"""
    HUMAN = "human"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MemoryUnitType(str, Enum):
    """记忆单元类型"""
    GLOBAL_MU = "global_mu"
    QUICK_MU = "quick_mu"
    CONVERSATION = "conversation"
    ERROR_LOG = "error_log"
    DECISION = "decision"
    CODE_SNIPPET = "code_snippet"
    DOCUMENTATION = "documentation"
    ARCHIVE = "archive"


class ProcessingStatus(str, Enum):
    """处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Pydantic 数据模型
class MessageModel(BaseModel):
    """消息模型"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    message_type: MessageType
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    token_count: int = 0
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class ConversationModel(BaseModel):
    """对话模型"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    title: str = ""
    messages: List[MessageModel] = []
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    message_count: int = 0
    token_count: int = 0
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class MemoryUnitModel(BaseModel):
    """记忆单元模型"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="memory_id")
    conversation_id: str
    unit_type: MemoryUnitType
    title: str
    summary: str
    content: str
    keywords: List[str] = []
    relevance_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
        populate_by_name = True


class EmbeddingModel(BaseModel):
    """嵌入向量模型"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_unit_id: str
    vector: List[float]
    model_name: str
    dimension: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True


# 搜索和检索相关模型
class SearchQuery(BaseModel):
    """搜索查询"""
    
    query: str = Field(description="搜索查询文本")
    query_type: str = Field(default="hybrid", description="查询类型")
    limit: int = Field(default=10, description="结果数量限制")
    min_score: float = Field(default=0.5, description="最小相关性分数")
    context: str = Field(default="", description="上下文信息")
    memory_types: Optional[List[MemoryUnitType]] = None
    
    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """搜索结果"""
    
    memory_unit: MemoryUnitModel
    relevance_score: float
    match_type: str = "semantic"
    matched_keywords: List[str] = []
    
    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """搜索响应"""
    
    results: List[SearchResult]
    total_count: int
    search_time_ms: float
    query_id: str
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


# 上下文注入相关模型
class ContextInjectionRequest(BaseModel):
    """上下文注入请求"""
    
    original_prompt: str
    query_text: Optional[str] = None
    context_hint: Optional[str] = None
    injection_mode: str = "balanced"
    max_tokens: int = 2000
    
    class Config:
        from_attributes = True


class ContextInjectionResponse(BaseModel):
    """上下文注入响应"""
    
    enhanced_prompt: str
    injected_memories: List[MemoryUnitModel]
    tokens_used: int
    processing_time_ms: float
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


# 健康状态和错误响应
class HealthStatus(BaseModel):
    """健康状态"""
    
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: Dict[str, bool] = {}
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """错误响应"""
    
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True


# SQLAlchemy 数据库模型
class ConversationDB(Base):
    """对话数据库模型"""
    
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), nullable=True)
    title = Column(String(500), nullable=False, default="")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, nullable=False, default=0)
    token_count = Column(Integer, nullable=False, default=0)
    meta_data = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    messages = relationship("MessageDB", back_populates="conversation", cascade="all, delete-orphan")
    memory_units = relationship("MemoryUnitDB", back_populates="conversation", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index("idx_conversations_session_id", "session_id"),
        Index("idx_conversations_started_at", "started_at"),
    )


class MessageDB(Base):
    """消息数据库模型"""
    
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    message_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    token_count = Column(Integer, nullable=False, default=0)
    meta_data = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 关系
    conversation = relationship("ConversationDB", back_populates="messages")
    
    # 索引
    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
        Index("idx_messages_timestamp", "timestamp"),
        Index("idx_messages_type", "message_type"),
    )


class MemoryUnitDB(Base):
    """记忆单元数据库模型"""
    
    __tablename__ = "memory_units"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    unit_type = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    keywords = Column(JSON, nullable=True)
    relevance_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    meta_data = Column("metadata", JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # 关系
    conversation = relationship("ConversationDB", back_populates="memory_units")
    embeddings = relationship("EmbeddingDB", back_populates="memory_unit", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index("idx_memory_units_conversation_id", "conversation_id"),
        Index("idx_memory_units_type", "unit_type"),
        Index("idx_memory_units_created_at", "created_at"),
        Index("idx_memory_units_active", "is_active"),
    )


class EmbeddingDB(Base):
    """嵌入向量数据库模型"""
    
    __tablename__ = "embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memory_unit_id = Column(UUID(as_uuid=True), ForeignKey("memory_units.id"), nullable=False)
    vector = Column(JSON, nullable=False)  # 存储为JSON数组
    model_name = Column(String(100), nullable=False)
    dimension = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 关系
    memory_unit = relationship("MemoryUnitDB", back_populates="embeddings")
    
    # 索引
    __table_args__ = (
        Index("idx_embeddings_memory_unit_id", "memory_unit_id"),
        Index("idx_embeddings_model", "model_name"),
    )


class CostTrackingDB(Base):
    """成本追踪数据库模型"""
    
    __tablename__ = "cost_tracking"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    operation_type = Column(String(50), nullable=False)  # embedding, completion, etc.
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    meta_data = Column("metadata", JSON, nullable=True)
    
    # 索引
    __table_args__ = (
        Index("idx_cost_tracking_provider", "provider"),
        Index("idx_cost_tracking_model", "model_name"),
        Index("idx_cost_tracking_timestamp", "timestamp"),
    )