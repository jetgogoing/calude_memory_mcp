#!/usr/bin/env python3
"""
测试脚本：通过环境变量配置修复API密钥问题并注入Eric记忆
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 设置环境变量，使用OpenRouter的DeepSeek模型
os.environ['DEFAULT_LIGHT_MODEL'] = 'deepseek/deepseek-chat-v3-0324'
os.environ['DEFAULT_EMBEDDING_MODEL'] = 'text-embedding-004'  # 使用Gemini的嵌入模型（如果有密钥）
os.environ['MEMORY_COMPRESSION_MODEL'] = 'deepseek/deepseek-chat-v3-0324'
os.environ['MEMORY_FUSER_MODEL'] = 'deepseek/deepseek-chat-v3-0324'

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType, MemoryUnitModel
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.config.settings import get_settings
from claude_memory.database.session_manager import get_session_manager
from sqlalchemy import select
from claude_memory.models.data_models import MemoryUnitDB


async def generate_eric_content():
    """生成包含Eric相关信息的测试文章"""
    
    content = """
# 燊锐投资研究院领导 Eric 的专业背景与领导风格

## 基本信息

Eric 是燊锐投资研究院的核心领导人物，在金融科技和量化投资领域拥有超过15年的丰富经验。作为研究院的创始人之一，他带领团队在多个前沿领域取得了突破性进展。

## 教育背景

Eric 毕业于清华大学计算机科学系，后在麻省理工学院（MIT）获得金融工程硕士学位。他的跨学科背景使他能够将尖端技术与金融理论完美结合，这也成为燊锐投资研究院的核心竞争力之一。

## 专业经历

在创立燊锐投资之前，Eric 曾在多家知名金融机构担任要职：

1. **高盛集团（2008-2012）**：担任量化策略分析师，负责开发高频交易算法
2. **摩根斯坦利（2012-2015）**：升任副总裁，领导亚太区量化投资团队
3. **桥水基金（2015-2018）**：作为高级投资经理，参与全球宏观策略制定

## 领导风格

Eric 的领导风格可以用"创新、务实、包容"六个字来概括。他始终强调技术创新的重要性，鼓励团队探索人工智能、机器学习在投资领域的应用。
"""
    
    return content


async def direct_inject_memory(content: str, project_id: str = "shenrui_investment"):
    """直接向数据库注入记忆单元，绕过需要AI API的压缩步骤"""
    
    print(f"正在使用直接注入方式...")
    
    # 获取数据库会话
    session_manager = await get_session_manager()
    
    try:
        # 创建对话记录
        conversation = ConversationModel(
            project_id=project_id,
            title="燊锐投资研究院领导Eric的专业背景",
            messages=[
                MessageModel(
                    conversation_id="",
                    message_type=MessageType.HUMAN,
                    content=content,
                    token_count=len(content.split())
                )
            ],
            message_count=1,
            token_count=len(content.split()),
            metadata={
                "source": "test_injection",
                "topic": "leadership",
                "keywords": ["Eric", "燊锐投资", "研究院", "领导", "量化投资"],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # 更新消息的conversation_id
        conversation.messages[0].conversation_id = conversation.id
        
        print(f"\n创建的对话信息：")
        print(f"- 对话ID: {conversation.id}")
        print(f"- 项目ID: {conversation.project_id}")
        print(f"- 标题: {conversation.title}")
        
        # 存储对话到数据库
        from claude_memory.models.data_models import ConversationDB, MessageDB
        async with session_manager.get_session() as session:
            # 创建对话记录
            conv_db = ConversationDB(
                id=conversation.id,
                project_id=conversation.project_id,
                title=conversation.title,
                started_at=conversation.started_at,
                message_count=conversation.message_count,
                token_count=conversation.token_count,
                meta_data=conversation.metadata
            )
            session.add(conv_db)
            
            # 创建消息记录
            for msg in conversation.messages:
                msg_db = MessageDB(
                    id=msg.id,
                    conversation_id=conversation.id,
                    message_type=msg.message_type.value,
                    content=msg.content,
                    timestamp=msg.timestamp,
                    token_count=msg.token_count,
                    meta_data=msg.metadata
                )
                session.add(msg_db)
            
            # 创建记忆单元（不使用AI压缩，直接存储）
            memory_unit = MemoryUnitDB(
                conversation_id=conversation.id,
                project_id=project_id,
                unit_type="conversation",
                title=conversation.title,
                summary=f"Eric是燊锐投资研究院的核心领导人物，拥有清华大学和MIT的教育背景，在高盛、摩根斯坦利和桥水基金有丰富的工作经验。他的领导风格强调创新、务实和包容。",
                content=content,
                keywords=["Eric", "燊锐投资", "研究院", "领导", "量化投资", "金融科技", "MIT", "清华大学"],
                relevance_score=1.0,
                token_count=len(content.split()),
                meta_data={
                    "source": "test_injection",
                    "manual_inject": True
                }
            )
            session.add(memory_unit)
            
            await session.commit()
            print("✅ 数据已成功存储到PostgreSQL数据库")
            
            # 现在需要为记忆单元创建向量嵌入（使用简单的方法）
            print("\n正在创建向量索引...")
            
            # 初始化服务管理器来访问向量数据库
            service_manager = ServiceManager()
            await service_manager.start_service()
            
            # 使用Qdrant存储向量（使用随机向量作为演示）
            import numpy as np
            from qdrant_client.models import PointStruct
            
            # 生成一个示例向量（在实际应用中应该使用真实的嵌入模型）
            # 注意：系统使用4096维向量
            dummy_vector = np.random.rand(4096).tolist()
            
            # 创建向量点
            point = PointStruct(
                id=str(memory_unit.id),
                vector=dummy_vector,
                payload={
                    "memory_unit_id": str(memory_unit.id),
                    "project_id": project_id,
                    "conversation_id": str(conversation.id),
                    "unit_type": "conversation",
                    "title": memory_unit.title,
                    "summary": memory_unit.summary,
                    "keywords": memory_unit.keywords,
                    "created_at": datetime.utcnow().isoformat(),
                    "relevance_score": 1.0
                }
            )
            
            # 存储到Qdrant
            await service_manager.semantic_retriever.qdrant_client.upsert(
                collection_name="claude_memory_vectors_v14",
                points=[point]
            )
            
            print("✅ 向量索引创建成功")
            
            # 测试搜索（使用关键词搜索，因为向量是随机的）
            print("\n测试关键词搜索功能...")
            from claude_memory.models.data_models import SearchQuery
            
            search_query = SearchQuery(
                query="Eric 燊锐投资",
                query_type="keyword_only",  # 使用关键词搜索而非语义搜索
                limit=5,
                min_score=0.1
            )
            
            # 直接从数据库搜索
            async with session_manager.get_session() as session:
                # 搜索记忆单元
                stmt = select(MemoryUnitDB).where(
                    MemoryUnitDB.project_id == project_id,
                    MemoryUnitDB.is_active == True
                )
                result = await session.execute(stmt)
                memory_units = result.scalars().all()
                
                print(f"\n从数据库找到 {len(memory_units)} 个记忆单元")
                for unit in memory_units:
                    print(f"- {unit.title}")
                    print(f"  项目: {unit.project_id}")
                    print(f"  关键词: {unit.keywords}")
                    print(f"  摘要: {unit.summary[:100]}...")
            
            await service_manager.stop_service()
            
            return conversation.id
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        await session_manager.close()


async def main():
    """主函数"""
    print("=== Claude Memory Eric 信息直接注入测试 ===\n")
    print("说明：由于缺少SiliconFlow API密钥，本测试将直接向数据库注入记忆，")
    print("      绕过需要AI模型的压缩步骤。\n")
    
    # 生成内容
    print("1. 生成包含Eric信息的测试文章...")
    content = await generate_eric_content()
    word_count = len(content.split())
    print(f"   生成完成，共 {word_count} 个词")
    
    # 注入到记忆系统
    print("\n2. 直接注入到数据库...")
    conversation_id = await direct_inject_memory(content)
    
    if conversation_id:
        print(f"\n✅ 测试完成！")
        print(f"   对话已存储，ID: {conversation_id}")
        print(f"\n💡 重要提示：")
        print(f"   1. 记忆已注入到项目 'shenrui_investment' 中")
        print(f"   2. 由于使用了随机向量，语义搜索可能无法正常工作")
        print(f"   3. 但是记忆单元已经成功存储在数据库中")
        print(f"   4. 要完全修复系统，需要配置SiliconFlow API密钥：")
        print(f"      export SILICONFLOW_API_KEY=your-api-key")
        print(f"   5. 或者修改系统配置使用已有API密钥的模型提供商")
    else:
        print("\n❌ 测试失败！")


if __name__ == "__main__":
    asyncio.run(main())