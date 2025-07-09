#!/usr/bin/env python3
"""
Claude Memory 核心组件测试
直接测试内部模块功能
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
import uuid
from typing import List

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# 导入核心模块
from claude_memory.models.data_models import (
    ConversationModel, MessageModel, MessageType, MemoryUnitModel, MemoryUnitType
)
from claude_memory.config.settings import get_settings
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.database.session_manager import get_session_manager
from sqlalchemy import select
import structlog

# 配置日志
logger = structlog.get_logger(__name__)

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

async def test_core_workflow():
    """测试核心工作流程"""
    
    print_header("Claude Memory 核心组件测试")
    
    # 初始化
    settings = get_settings()
    session_manager = get_session_manager()
    service_manager = ServiceManager(settings=settings, session_manager=session_manager)
    
    print_success("服务管理器初始化成功")
    
    # 步骤1: 创建测试对话
    print_step(1, "创建测试对话")
    
    # 创建对话对象
    conversation = ConversationModel(
        id=str(uuid.uuid4()),
        project_id="test_project",
        session_id="test_session",
        title="测试对话",
        started_at=datetime.utcnow()
    )
    
    # 创建消息
    messages = [
        MessageModel(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            message_type=MessageType.HUMAN,
            content="你好！我想了解如何使用Python进行机器学习。",
            timestamp=datetime.utcnow()
        ),
        MessageModel(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            message_type=MessageType.ASSISTANT,
            content="""很高兴帮助你学习Python机器学习！以下是入门建议：

1. **基础准备**：
   - 确保掌握Python基础语法
   - 了解NumPy和Pandas库

2. **核心库学习**：
   - Scikit-learn：最常用的机器学习库
   - TensorFlow/PyTorch：深度学习框架

3. **学习路径**：
   - 从简单的分类和回归开始
   - 逐步学习更复杂的算法
   - 实践项目很重要

4. **推荐资源**：
   - Andrew Ng的机器学习课程
   - Hands-On Machine Learning书籍""",
            timestamp=datetime.utcnow()
        ),
        MessageModel(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            message_type=MessageType.HUMAN,
            content="Scikit-learn和TensorFlow有什么区别？",
            timestamp=datetime.utcnow()
        ),
        MessageModel(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            message_type=MessageType.ASSISTANT,
            content="""主要区别如下：

**Scikit-learn**：
- 传统机器学习算法（决策树、SVM、随机森林等）
- 简单易用，API统一
- 适合中小规模数据
- 不支持GPU加速

**TensorFlow**：
- 深度学习框架
- 支持构建复杂的神经网络
- 适合大规模数据和GPU加速
- 学习曲线较陡峭

简而言之：Scikit-learn适合传统ML，TensorFlow适合深度学习。""",
            timestamp=datetime.utcnow()
        )
    ]
    
    conversation.messages = messages
    print_success(f"创建对话 {conversation.id} 包含 {len(messages)} 条消息")
    
    # 步骤2: 保存对话到数据库
    print_step(2, "保存对话到数据库")
    
    async with session_manager.get_async_session() as session:
        try:
            session.add(conversation)
            await session.commit()
            print_success("对话保存到 PostgreSQL 成功")
        except Exception as e:
            print_error(f"保存对话失败: {e}")
            await session.rollback()
            return
    
    # 步骤3: 处理对话（生成记忆单元）
    print_step(3, "处理对话生成记忆单元")
    
    try:
        memory_units = await service_manager.process_conversation(conversation.id)
        print_success(f"生成 {len(memory_units)} 个记忆单元")
        
        for i, unit in enumerate(memory_units, 1):
            print_info(f"  记忆单元 {i}:")
            print_info(f"    - 类型: {unit.unit_type}")
            print_info(f"    - 内容长度: {len(unit.content)} 字符")
            print_info(f"    - 质量分数: {unit.quality_score:.2f}")
            
    except Exception as e:
        print_error(f"处理对话失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 步骤4: 测试语义搜索
    print_step(4, "测试语义搜索")
    
    # 等待一下确保向量索引更新
    await asyncio.sleep(2)
    
    test_queries = [
        "如何学习Python机器学习",
        "Scikit-learn和TensorFlow的区别",
        "机器学习入门建议"
    ]
    
    for query in test_queries:
        print_info(f"\n搜索: '{query}'")
        try:
            results = await service_manager.search_memories(
                query=query,
                project_id="test_project",
                limit=3
            )
            
            print_success(f"找到 {len(results)} 个相关记忆")
            for i, result in enumerate(results, 1):
                print_info(f"  [{i}] 相似度: {result.score:.3f}")
                print_info(f"      类型: {result.memory_unit.unit_type}")
                print_info(f"      预览: {result.memory_unit.content[:80]}...")
                
        except Exception as e:
            print_error(f"搜索失败: {e}")
    
    # 步骤5: 测试记忆注入
    print_step(5, "测试记忆注入（上下文增强）")
    
    test_prompt = "我是初学者，想系统学习Python机器学习，应该怎么开始？"
    
    try:
        enhanced_context = await service_manager.inject_memories(
            prompt=test_prompt,
            project_id="test_project",
            max_memories=5
        )
        
        print_success("记忆注入成功")
        print_info(f"增强后的上下文长度: {len(enhanced_context)} 字符")
        print_info("\n增强后的上下文预览:")
        print(f"{Colors.YELLOW}{enhanced_context[:600]}...{Colors.ENDC}")
        
    except Exception as e:
        print_error(f"记忆注入失败: {e}")
    
    # 步骤6: 查看统计信息
    print_step(6, "获取项目统计信息")
    
    async with session_manager.get_async_session() as session:
        try:
            # 统计对话数
            conv_count = await session.execute(
                select(ConversationModel).where(ConversationModel.project_id == "test_project")
            )
            conversations = conv_count.scalars().all()
            
            # 统计记忆单元数
            mem_count = await session.execute(
                select(MemoryUnitModel).where(MemoryUnitModel.project_id == "test_project")
            )
            memories = mem_count.scalars().all()
            
            print_success("项目统计:")
            print_info(f"  - 对话总数: {len(conversations)}")
            print_info(f"  - 记忆单元总数: {len(memories)}")
            
            # 按类型统计
            type_counts = {}
            for mem in memories:
                type_counts[mem.unit_type] = type_counts.get(mem.unit_type, 0) + 1
            
            print_info("  - 记忆单元类型分布:")
            for unit_type, count in type_counts.items():
                print_info(f"      {unit_type}: {count}")
                
        except Exception as e:
            print_error(f"获取统计失败: {e}")
    
    # 步骤7: 清理测试数据（可选）
    print_step(7, "清理测试数据")
    
    cleanup = input("\n是否清理测试数据？(y/n): ").lower().strip()
    if cleanup == 'y':
        async with session_manager.get_async_session() as session:
            try:
                # 删除记忆单元
                await session.execute(
                    select(MemoryUnitModel).where(MemoryUnitModel.conversation_id == conversation.id)
                )
                memories_to_delete = (await session.execute(
                    select(MemoryUnitModel).where(MemoryUnitModel.conversation_id == conversation.id)
                )).scalars().all()
                
                for mem in memories_to_delete:
                    await session.delete(mem)
                
                # 删除对话
                conv_to_delete = await session.get(ConversationModel, conversation.id)
                if conv_to_delete:
                    await session.delete(conv_to_delete)
                
                await session.commit()
                print_success("测试数据已清理")
                
            except Exception as e:
                print_error(f"清理失败: {e}")
                await session.rollback()
    else:
        print_info("保留测试数据")
    
    print_header("测试完成")
    print_success("核心组件工作正常！")

async def main():
    """主函数"""
    try:
        await test_core_workflow()
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print_error(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())