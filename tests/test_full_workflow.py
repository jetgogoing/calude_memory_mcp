#!/usr/bin/env python3
"""
Claude Memory 系统集成测试脚本
测试完整的工作流程：收集 -> 压缩 -> 存储 -> 检索 -> 融合
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# 导入所需模块
from claude_memory.collectors.conversation_collector import ConversationCollector
from claude_memory.processors.semantic_compressor import SemanticCompressor
from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.fusers.memory_fuser import MemoryFuser
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import (
    Conversation,
    Message,
    MessageRole,
    MemoryUnit,
    MemoryUnitType
)
from claude_memory.config.settings import get_settings
from claude_memory.database.session_manager import get_session_manager
from sqlalchemy import select
import requests

# 彩色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")

def print_step(step, text):
    print(f"{Colors.BLUE}[步骤 {step}] {text}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.YELLOW}→ {text}{Colors.ENDC}")

# 测试数据
TEST_CONVERSATIONS = [
    {
        "id": "test_conv_1",
        "messages": [
            {"role": "user", "content": "我想学习如何使用Python进行数据分析"},
            {"role": "assistant", "content": "学习Python数据分析是个很好的选择！我建议从以下几个方面开始：\n1. 基础库：NumPy和Pandas\n2. 可视化：Matplotlib和Seaborn\n3. 统计分析：SciPy\n4. 机器学习：Scikit-learn"},
            {"role": "user", "content": "Pandas和NumPy有什么区别？"},
            {"role": "assistant", "content": "NumPy主要用于数值计算和多维数组操作，而Pandas建立在NumPy基础上，专门用于数据处理和分析，提供了DataFrame等高级数据结构。"}
        ]
    },
    {
        "id": "test_conv_2",
        "messages": [
            {"role": "user", "content": "请帮我解释一下Claude Memory系统的架构"},
            {"role": "assistant", "content": "Claude Memory系统采用双层存储架构：\n1. PostgreSQL用于持久化存储对话历史\n2. Qdrant向量数据库用于语义检索\n系统通过语义压缩将对话转换为记忆单元，支持高效的相似度搜索。"},
            {"role": "user", "content": "这个系统能存储多长时间的对话？"},
            {"role": "assistant", "content": "系统可以永久存储所有对话历史。默认情况下，记忆单元会根据配置的TTL进行清理，但原始对话数据始终保留在PostgreSQL中。"}
        ]
    },
    {
        "id": "test_conv_3",
        "messages": [
            {"role": "user", "content": "如何部署Claude Memory到生产环境？"},
            {"role": "assistant", "content": "部署到生产环境需要：\n1. 配置环境变量（.env文件）\n2. 设置PostgreSQL和Qdrant数据库\n3. 使用Docker Compose或Kubernetes\n4. 配置反向代理和SSL证书\n5. 设置监控和日志收集"},
            {"role": "user", "content": "有没有一键部署脚本？"},
            {"role": "assistant", "content": "是的，项目提供了deploy/scripts/deploy_production.sh脚本，可以自动完成大部分部署步骤。"}
        ]
    }
]

async def test_workflow():
    """测试完整工作流程"""
    
    print_header("Claude Memory 系统集成测试")
    
    # 初始化服务管理器
    settings = get_settings()
    session_manager = get_session_manager()
    service_manager = ServiceManager(
        settings=settings,
        session_manager=session_manager
    )
    
    # 测试数据库连接
    print_step(0, "测试数据库连接")
    try:
        # PostgreSQL
        async with session_manager.get_async_session() as session:
            result = await session.execute(select(1))
            print_success("PostgreSQL 连接正常")
        
        # Qdrant
        response = requests.get(f"{settings.qdrant_url}/collections")
        if response.status_code == 200:
            print_success("Qdrant 连接正常")
        else:
            print_error(f"Qdrant 连接失败: {response.status_code}")
    except Exception as e:
        print_error(f"数据库连接失败: {e}")
        return
    
    # 步骤1: 初始化组件
    print_step(1, "初始化系统组件")
    collector = ConversationCollector()
    compressor = SemanticCompressor(settings=settings)
    retriever = SemanticRetriever(settings=settings)
    fuser = MemoryFuser(settings=settings)
    
    print_success("所有组件初始化成功")
    
    # 步骤2: 收集对话
    print_step(2, "测试 ConversationCollector - 收集对话")
    collected_conversations = []
    
    for conv_data in TEST_CONVERSATIONS:
        messages = [
            Message(
                role=MessageRole(msg["role"]),
                content=msg["content"],
                conversation_id=conv_data["id"],
                created_at=datetime.utcnow()
            )
            for msg in conv_data["messages"]
        ]
        
        conversation = Conversation(
            id=conv_data["id"],
            project_id="test_project",
            user_id="test_user",
            messages=messages,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # 收集对话
        collected = await collector.collect_conversation(conversation)
        if collected:
            collected_conversations.append(collected)
            print_success(f"收集对话 {conv_data['id']} - {len(messages)} 条消息")
        else:
            print_error(f"收集对话 {conv_data['id']} 失败")
    
    print_info(f"共收集 {len(collected_conversations)} 个对话")
    
    # 步骤3: 压缩对话为记忆单元
    print_step(3, "测试 SemanticCompressor - 压缩对话")
    memory_units = []
    
    for conversation in collected_conversations:
        try:
            # 压缩对话
            compressed_units = await compressor.compress_conversation(conversation)
            memory_units.extend(compressed_units)
            print_success(f"压缩对话 {conversation.id} -> {len(compressed_units)} 个记忆单元")
            
            # 显示记忆单元详情
            for unit in compressed_units:
                print_info(f"  - 类型: {unit.unit_type}, 内容长度: {len(unit.content)}")
                
        except Exception as e:
            print_error(f"压缩对话 {conversation.id} 失败: {e}")
    
    print_info(f"共生成 {len(memory_units)} 个记忆单元")
    
    # 步骤4: 存储到数据库
    print_step(4, "测试存储到 PostgreSQL 和 Qdrant")
    stored_units = []
    
    async with session_manager.get_async_session() as session:
        for unit in memory_units:
            try:
                # 存储到 PostgreSQL
                session.add(unit)
                await session.commit()
                
                # 获取生成的 ID
                await session.refresh(unit)
                stored_units.append(unit)
                
                print_success(f"存储记忆单元 {unit.id} 到 PostgreSQL")
                
            except Exception as e:
                print_error(f"存储记忆单元失败: {e}")
                await session.rollback()
    
    # 存储到 Qdrant（通过 ServiceManager）
    for unit in stored_units:
        try:
            await service_manager._store_to_qdrant(unit)
            print_success(f"存储记忆单元 {unit.id} 到 Qdrant")
        except Exception as e:
            print_error(f"存储到 Qdrant 失败: {e}")
    
    print_info(f"成功存储 {len(stored_units)} 个记忆单元")
    
    # 等待一下确保索引更新
    await asyncio.sleep(2)
    
    # 步骤5: 语义检索
    print_step(5, "测试 SemanticRetriever - 语义检索")
    test_queries = [
        "如何学习Python数据分析",
        "Claude Memory的架构是什么",
        "怎么部署到生产环境",
        "Pandas和NumPy的区别"
    ]
    
    for query in test_queries:
        print_info(f"\n查询: '{query}'")
        try:
            # 语义检索
            results = await retriever.retrieve(
                query=query,
                project_id="test_project",
                limit=3
            )
            
            print_success(f"检索到 {len(results)} 个相关记忆")
            for i, result in enumerate(results, 1):
                print_info(f"  [{i}] 相似度: {result.score:.3f}")
                print_info(f"      类型: {result.memory_unit.unit_type}")
                print_info(f"      内容预览: {result.memory_unit.content[:100]}...")
                
        except Exception as e:
            print_error(f"检索失败: {e}")
    
    # 步骤6: 记忆融合
    print_step(6, "测试 MemoryFuser - 记忆融合")
    test_prompt = "我想了解如何使用Python进行数据分析，特别是Pandas的使用"
    
    try:
        # 先检索相关记忆
        search_results = await retriever.retrieve(
            query=test_prompt,
            project_id="test_project",
            limit=5
        )
        
        print_info(f"为融合检索到 {len(search_results)} 个记忆")
        
        # 融合记忆
        fused_context = await fuser.fuse_memories(
            memories=search_results,
            query=test_prompt
        )
        
        print_success("记忆融合成功")
        print_info(f"融合后的上下文长度: {len(fused_context)} 字符")
        print_info("\n融合后的上下文预览:")
        print(f"{Colors.YELLOW}{fused_context[:500]}...{Colors.ENDC}")
        
    except Exception as e:
        print_error(f"记忆融合失败: {e}")
    
    # 步骤7: 清理测试数据
    print_step(7, "清理测试数据")
    async with session_manager.get_async_session() as session:
        try:
            # 删除测试记忆单元
            for unit in stored_units:
                await session.delete(unit)
            
            # 删除测试对话
            for conv in collected_conversations:
                await session.delete(conv)
            
            await session.commit()
            print_success("测试数据清理完成")
            
        except Exception as e:
            print_error(f"清理失败: {e}")
            await session.rollback()
    
    # 从 Qdrant 删除测试数据
    try:
        collection_name = f"claude_memory_vectors_v{settings.vector_db_version}"
        for unit in stored_units:
            requests.delete(
                f"{settings.qdrant_url}/collections/{collection_name}/points/{unit.id}"
            )
        print_success("Qdrant 测试数据清理完成")
    except Exception as e:
        print_error(f"Qdrant 清理失败: {e}")
    
    print_header("测试完成")
    print_success("所有组件工作正常！")


async def main():
    """主函数"""
    try:
        await test_workflow()
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print_error(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())