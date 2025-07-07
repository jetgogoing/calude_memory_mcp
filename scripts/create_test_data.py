#!/usr/bin/env python3
"""
Claude记忆管理MCP服务 - 创建测试数据脚本

功能：
1. 在数据库中创建一些样本记忆单元
2. 为v1.4迁移测试提供数据
3. 包含不同类型的记忆单元
"""

import sys
import asyncio
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from claude_memory.config.settings import get_settings
from claude_memory.models.data_models import ConversationDB, MessageDB, MemoryUnitDB

async def create_test_data():
    """创建测试数据"""
    settings = get_settings()
    
    print(f"Creating test data in: {settings.database.database_url}")
    
    # 使用正确的数据库URL
    database_url = settings.database.database_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(database_url)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # 创建测试对话
            conversation_1 = ConversationDB(
                id=uuid.uuid4(),
                session_id="test_session_1",
                project_id="claude_memory_test",
                title="Claude记忆系统架构讨论",
                message_count=5,
                token_count=1200,
                status="completed",
                created_at=datetime.utcnow() - timedelta(days=2),
                last_activity_at=datetime.utcnow() - timedelta(days=1)
            )
            
            conversation_2 = ConversationDB(
                id=uuid.uuid4(),
                session_id="test_session_2", 
                project_id="claude_memory_test",
                title="向量数据库性能优化",
                message_count=8,
                token_count=2100,
                status="completed",
                created_at=datetime.utcnow() - timedelta(days=1),
                last_activity_at=datetime.utcnow() - timedelta(hours=12)
            )
            
            session.add(conversation_1)
            session.add(conversation_2)
            await session.flush()  # 获取生成的ID
            
            # 创建测试记忆单元
            memory_units = [
                MemoryUnitDB(
                    id=uuid.uuid4(),
                    conversation_id=conversation_1.id,
                    unit_type="global",
                    title="Claude记忆系统四层架构",
                    summary="系统采用数据采集层、语义处理层、存储检索层、智能注入层的四层架构设计，确保高效的记忆管理和上下文注入能力。",
                    content="在Claude记忆管理系统的设计中，我们采用了清晰的四层架构：\n1. 数据采集层：负责捕获Claude CLI对话，支持多种捕获方式\n2. 语义处理层：使用多模型协作进行语义压缩和提取\n3. 存储检索层：结合Qdrant向量数据库和PostgreSQL实现高效存储\n4. 智能注入层：动态构建上下文，智能注入相关记忆\n\n每层都有明确的职责分工，通过标准接口进行交互，确保系统的可维护性和扩展性。",
                    keywords=["架构设计", "四层架构", "数据采集", "语义处理", "向量存储", "上下文注入"],
                    relevance_score=0.95,
                    token_count=280,
                    quality_score=0.92,
                    is_active=True,
                    created_at=datetime.utcnow() - timedelta(days=2)
                ),
                MemoryUnitDB(
                    id=uuid.uuid4(),
                    conversation_id=conversation_1.id,
                    unit_type="global",
                    title="多模型API策略",
                    summary="系统集成Gemini、OpenRouter、SiliconFlow三种API，通过模型池和自动降级策略确保服务稳定性，有效控制成本。",
                    content="为确保API服务的稳定性和成本控制，系统实施多模型API策略：\n\n**API提供商：**\n- Gemini API：用于重型任务，如深度语义分析\n- OpenRouter API：提供多样化模型选择，平衡性能和成本\n- SiliconFlow API：主要用于Qwen3系列模型，成本效益高\n\n**策略特点：**\n- 模型池管理：根据任务类型自动选择最适合的模型\n- 自动降级：当高优先级API不可用时，自动切换到备用API\n- 成本控制：动态分配API预算，确保日成本控制在$0.3-0.5\n- 智能路由：根据任务复杂度和可用预算选择最优API",
                    keywords=["多模型", "API策略", "模型池", "自动降级", "成本控制", "Gemini", "OpenRouter", "SiliconFlow"],
                    relevance_score=0.88,
                    token_count=350,
                    quality_score=0.89,
                    is_active=True,
                    created_at=datetime.utcnow() - timedelta(days=2)
                ),
                MemoryUnitDB(
                    id=uuid.uuid4(),
                    conversation_id=conversation_2.id,
                    unit_type="global",
                    title="Qdrant向量数据库优化策略",
                    summary="通过混合检索、向量压缩、批量操作等技术优化Qdrant性能，实现150ms内的语义检索延迟目标。",
                    content="为满足v1.4的性能要求（≤150ms语义检索延迟），实施以下Qdrant优化策略：\n\n**检索优化：**\n- 混合检索：结合向量相似度和关键词匹配\n- Top-20→Top-5策略：初检20个结果，重排序后返回前5个\n- 预过滤：基于时间戳、项目ID等元数据预筛选\n\n**存储优化：**\n- 向量压缩：使用4096维Qwen3-Embedding-8B模型\n- 分片策略：按项目和时间维度进行数据分片\n- 索引优化：HNSW参数调优，平衡精度和速度\n\n**缓存策略：**\n- 查询结果缓存：常用查询结果缓存1小时\n- 向量缓存：热点向量常驻内存\n- 连接池优化：复用HTTP连接，减少延迟",
                    keywords=["Qdrant优化", "混合检索", "向量压缩", "性能优化", "HNSW", "缓存策略"],
                    relevance_score=0.91,
                    token_count=420,
                    quality_score=0.90,
                    is_active=True,
                    created_at=datetime.utcnow() - timedelta(days=1)
                ),
                MemoryUnitDB(
                    id=uuid.uuid4(),
                    conversation_id=conversation_2.id,
                    unit_type="global", 
                    title="v1.4版本Qwen3模型集成",
                    summary="v1.4版本升级到Qwen3-Embedding-8B（4096维）和Qwen3-Reranker-8B，显著提升语义理解能力和检索精度。",
                    content="v1.4版本的核心升级是引入Qwen3模型系列：\n\n**Qwen3-Embedding-8B特性：**\n- 向量维度：4096维（相比v1.3的1536维大幅提升）\n- 语义理解：支持更细粒度的语义表示\n- 多语言：中英文双语优化\n- 性能：在多个基准测试中超越OpenAI text-embedding-ada-002\n\n**Qwen3-Reranker-8B特性：**\n- 重排序：对初检结果进行智能重排序\n- 上下文理解：更好理解查询意图和文档相关性\n- 精度提升：Top-5准确率相比简单向量检索提升15-20%\n\n**迁移策略：**\n- 渐进式迁移：先创建新集合，再批量迁移数据\n- 断点续传：支持迁移中断后从断点继续\n- 数据验证：确保迁移后数据完整性和一致性",
                    keywords=["Qwen3", "模型升级", "向量维度", "重排序", "语义理解", "数据迁移"],
                    relevance_score=0.94,
                    token_count=380,
                    quality_score=0.93,
                    is_active=True,
                    created_at=datetime.utcnow() - timedelta(hours=12)
                )
            ]
            
            for memory_unit in memory_units:
                session.add(memory_unit)
            
            await session.commit()
            
            print(f"✅ 创建测试数据成功:")
            print(f"   - 对话数量: 2")
            print(f"   - 记忆单元数量: {len(memory_units)}")
            print(f"   - 涵盖主题: 系统架构、API策略、性能优化、模型升级")
            
    except Exception as e:
        print(f"❌ 创建测试数据失败: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    # 确保使用正确的环境变量
    import os
    if "DATABASE__DATABASE_URL" not in os.environ:
        os.environ["DATABASE__DATABASE_URL"] = "postgresql://claude_memory:password@localhost:5432/claude_memory_db"
    
    asyncio.run(create_test_data())