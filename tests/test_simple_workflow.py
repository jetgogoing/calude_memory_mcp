#!/usr/bin/env python3
"""
Claude Memory 简化的系统测试
通过 ServiceManager 测试核心功能
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
from claude_memory.config.settings import get_settings
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import (
    ConversationModel, MessageModel, MessageType, SearchQuery, ContextInjectionRequest
)
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

async def test_workflow():
    """测试完整工作流程"""
    
    print_header("Claude Memory 简化系统测试")
    
    # 初始化
    settings = get_settings()
    service_manager = ServiceManager()
    
    print_success("服务管理器初始化成功")
    
    # 启动服务（初始化所有组件）
    print_info("正在初始化服务组件...")
    await service_manager._initialize_components()
    print_success("所有组件初始化完成")
    
    # 步骤1: 创建测试对话数据
    print_step(1, "创建测试对话")
    
    conversation_id = str(uuid.uuid4())
    project_id = "test_project"
    
    # 创建对话模型
    conversation = ConversationModel(
        id=conversation_id,
        project_id=project_id,
        session_id="test_session",
        title="Python机器学习讨论",
        messages=[],
        started_at=datetime.utcnow(),
        message_count=0,
        token_count=0
    )
    
    # 创建消息
    messages = [
        MessageModel(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            message_type=MessageType.HUMAN,
            content="你好！我想了解如何使用Python进行机器学习。",
            timestamp=datetime.utcnow()
        ),
        MessageModel(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
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
            conversation_id=conversation_id,
            message_type=MessageType.HUMAN,
            content="Scikit-learn和TensorFlow有什么区别？",
            timestamp=datetime.utcnow()
        ),
        MessageModel(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
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
    conversation.message_count = len(messages)
    
    print_success(f"创建对话 {conversation_id} 包含 {len(messages)} 条消息")
    
    # 步骤2: 存储对话
    print_step(2, "存储对话到系统")
    
    try:
        # 使用 ServiceManager 存储对话
        success = await service_manager.store_conversation(conversation)
        if success:
            print_success(f"对话存储成功，ID: {conversation_id}")
        else:
            print_error("对话存储失败")
            return
    except Exception as e:
        print_error(f"存储对话失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 等待一下确保向量索引更新
    print_info("\n等待向量索引更新...")
    await asyncio.sleep(3)
    
    # 步骤3: 测试语义搜索
    print_step(3, "测试语义搜索")
    
    test_queries = [
        "如何学习Python机器学习",
        "Scikit-learn和TensorFlow的区别",
        "机器学习入门建议"
    ]
    
    for query_text in test_queries:
        print_info(f"\n搜索: '{query_text}'")
        try:
            # 创建搜索查询对象
            search_query = SearchQuery(
                query=query_text,
                limit=3,
                min_score=0.5
            )
            
            results = await service_manager.search_memories(
                query=search_query,
                project_id=project_id
            )
            
            print_success(f"找到 {len(results.results)} 个相关记忆")
            for i, result in enumerate(results.results, 1):
                print_info(f"  [{i}] 相似度: {result.relevance_score:.3f}")
                print_info(f"      类型: {result.memory_unit.unit_type}")
                print_info(f"      标题: {result.memory_unit.title}")
                
        except Exception as e:
            print_error(f"搜索失败: {e}")
    
    # 步骤4: 测试记忆注入
    print_step(4, "测试记忆注入（上下文增强）")
    
    test_prompt = "我是初学者，想系统学习Python机器学习，应该怎么开始？"
    
    try:
        # 创建注入请求
        injection_request = ContextInjectionRequest(
            original_prompt=test_prompt,
            injection_mode="balanced",
            max_tokens=2000
        )
        
        # 执行注入
        injection_response = await service_manager.inject_context(injection_request)
        
        print_success("记忆注入成功")
        print_info(f"增强后的上下文长度: {len(injection_response.enhanced_prompt)} 字符")
        print_info(f"注入的记忆数量: {len(injection_response.injected_memories)}")
        print_info(f"使用的Token数: {injection_response.tokens_used}")
        print_info("\n增强后的上下文预览:")
        print(f"{Colors.YELLOW}{injection_response.enhanced_prompt[:600]}...{Colors.ENDC}")
        
    except Exception as e:
        print_error(f"记忆注入失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 步骤5: 获取服务状态
    print_step(5, "获取服务状态")
    
    try:
        status = await service_manager.get_service_status()
        print_success("服务状态:")
        print_info(f"  - 状态: {status.status}")
        print_info(f"  - 版本: {status.version}")
        print_info(f"  - 运行时间: {status.metrics.uptime_seconds:.2f} 秒")
        print_info(f"  - 处理的对话: {status.metrics.conversations_processed}")
        print_info(f"  - 创建的记忆: {status.metrics.memories_created}")
        print_info(f"  - 检索的记忆: {status.metrics.memories_retrieved}")
        print_info(f"  - 注入的上下文: {status.metrics.contexts_injected}")
        
    except Exception as e:
        print_error(f"获取统计失败: {e}")
    
    print_header("测试完成")
    print_success("核心组件工作流程测试完成！")

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