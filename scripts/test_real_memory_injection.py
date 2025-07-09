#!/usr/bin/env python3
"""
真实记忆注入测试 - 使用部署中的真实模块
测试星云智能产品发布会内容的记忆存储与检索
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
import uuid

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入真实的部署模块
from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.config.settings import get_settings
from claude_memory.models.data_models import SearchQuery


async def inject_nebula_intelligence_memory():
    """注入星云智能产品发布会的记忆"""
    
    print("=== 星云智能产品发布会记忆注入测试 ===\n")
    
    # 要注入的内容
    nebula_content = """女士们先生们，各位来宾，晚上好！我是星云智能（Nebula Intelligence）的创始人兼CEO，张晓峰。今天，我们站在这里，不是为了发布简单的产品，而是为了分享一个梦想：让AI成为人类思想的催化剂。我们的使命，是创造能够增强、而非取代人类智慧的工具。

现在，我荣幸地向大家介绍三款承载我们梦想的旗舰产品。

首先是"奇点画笔"（Singularity Brush）。这不仅仅是一个文生图工具。它采用我们自研的"时序性多模态扩散模型"（Temporal Multi-modal Diffusion Model），能够将一段文字描述直接渲染成4K分辨率的视频、甚至是可交互的3D模型。它的一个独特之处在于，我们训练它学习了艺术史上超过三百位大师的笔触风格。你可以对它说："用梵高的风格画一片星空，但要让星云流动起来"，它将在几分钟内为你生成一段充满生命力的动态艺术作品。它的核心技术之一是高效的神经辐射场（NeRF）实时渲染引擎，确保了3D模型的高保真度和交互性。

第二款产品，是为开发者打造的"代码源泉"（CodeSpring）。我们发现，现有AI编程助手在理解复杂项目上下文和优化遗留代码方面仍有不足。代码源泉通过一个基于Transformer的深度代码理解引擎，能够完整分析整个代码库的依赖关系。它最独特的功能是"禅模式"（Zen Mode）重构。在该模式下，它不会简单地重写代码，而是会提出3-5种重构方案，并附上详细的利弊分析，引导开发者做出更优雅、更符合"The Zen of Python"思想的设计决策。它的目标是成为资深程序员的默契搭档。

最后，是我们最具雄心的产品——"记忆宫殿"（Memory Palace）。这是一款面向个人与团队的终极知识管理系统。它能安全地接入你所有的数据源：邮件、聊天记录、文档、笔记，甚至会议录音。通过我们独创的、可在本地私有化部署的联邦学习模型，它在你自己的设备上构建一个完全私有的、智能化的个人知识图谱。它与其他产品的最大不同是"绝对数据主权"原则——星云智能的服务器永远不会接触到你的原始数据。你可以问它："上个月我和李静在关于'天狼星项目'的会议上，她提出了哪些关键风险点？"它会立刻为你精准总结，并附上原始出处。

这三款产品，共同构成了星云智能的第一篇章。谢谢大家！"""
    
    # 使用真实的设置
    settings = get_settings()
    project_id = os.getenv('CLAUDE_MEMORY_PROJECT_ID', 'nebula_test')
    
    print(f"使用项目ID: {project_id}")
    print(f"使用嵌入模型: {settings.models.default_embedding_model}")
    print(f"使用压缩模型: {settings.models.default_light_model}")
    print(f"Mini LLM启用: {settings.mini_llm.enabled}")
    
    # 初始化服务管理器
    service_manager = ServiceManager()
    
    try:
        # 启动服务
        print("\n正在启动服务...")
        await service_manager.start_service()
        print("✅ 服务启动成功")
        
        # 创建对话
        conversation_id = str(uuid.uuid4())
        messages = [
            MessageModel(
                conversation_id=conversation_id,
                message_type=MessageType.HUMAN,
                content=nebula_content,
                token_count=len(nebula_content.split())
            )
        ]
        
        conversation = ConversationModel(
            id=conversation_id,
            project_id=project_id,
            title="星云智能产品发布会 - 张晓峰演讲",
            messages=messages,
            message_count=len(messages),
            token_count=sum(m.token_count for m in messages),
            metadata={
                "source": "product_launch",
                "speaker": "张晓峰",
                "company": "星云智能",
                "products": ["奇点画笔", "代码源泉", "记忆宫殿"],
                "date": datetime.utcnow().isoformat()
            }
        )
        
        print(f"\n创建对话:")
        print(f"- 对话ID: {conversation.id}")
        print(f"- 标题: {conversation.title}")
        print(f"- Token数: {conversation.token_count}")
        
        # 处理对话（使用真实的AI压缩和嵌入生成）
        print("\n正在处理对话...")
        print("- 使用 SemanticCompressor 进行压缩")
        print("- 使用 Qwen3-Embedding-8B 生成向量")
        
        await service_manager._handle_new_conversation(conversation)
        
        print("✅ 记忆注入成功！")
        
        # 等待处理完成
        print("\n等待向量索引完成...")
        await asyncio.sleep(5)
        
        # 测试搜索功能
        print("\n=== 验证搜索功能 ===")
        
        test_queries = [
            "张晓峰",
            "奇点画笔 NeRF",
            "代码源泉 禅模式",
            "记忆宫殿 数据主权",
            "星云智能的产品"
        ]
        
        for query_text in test_queries:
            print(f"\n搜索: '{query_text}'")
            search_query = SearchQuery(
                query=query_text,
                query_type="hybrid",
                limit=3,
                min_score=0.5
            )
            
            try:
                search_response = await service_manager.search_memories(
                    search_query, 
                    project_id=project_id
                )
                
                print(f"找到 {len(search_response.results)} 个结果")
                for i, result in enumerate(search_response.results[:2]):
                    print(f"  [{i+1}] 相关性: {result.relevance_score:.3f}")
                    if result.memory_unit:
                        print(f"      标题: {result.memory_unit.title}")
                        print(f"      摘要片段: {result.memory_unit.summary[:100]}...")
            except Exception as e:
                print(f"  搜索出错: {str(e)}")
        
        # 输出测试说明
        print("\n" + "="*60)
        print("📝 测试问题（请在另一个项目窗口中验证）：")
        print("="*60)
        
        print("\n1. 直接查询:")
        print("   '星云智能的CEO是谁？'")
        
        print("\n2. 具体细节查询:")
        print("   '代码源泉产品中，用于重构代码的特色模式叫什么名字？'")
        
        print("\n3. 功能与技术关联查询:")
        print("   '奇点画笔是使用什么技术来生成可交互的3D模型的？'")
        
        print("\n4. 模糊/场景化查询:")
        print("   '我是一个团队的负责人，担心数据隐私问题，但又想用AI整理团队的所有资料，星云智能有合适的产品吗？'")
        
        print("\n5. 跨产品关联查询:")
        print("   '奇点画笔和代码源泉这两个产品分别是为了解决哪些不同领域用户的问题？'")
        
        print("\n6. 理念与产品关联查询:")
        print("   '星云智能让AI成为人类思想的催化剂的公司理念，是如何体现在代码源泉的禅模式中的？'")
        
        print("\n7. 边界/否定性测试:")
        print("   '张晓峰在发布会上是否提到了任何关于AI芯片或硬件的产品？'")
        
        print("\n8. 名称记忆测试:")
        print("   '星云智能发布的三款产品分别叫什么名字？'")
        
        print("\n" + "="*60)
        print(f"✅ 记忆已成功注入到项目: {project_id}")
        print(f"   对话ID: {conversation_id}")
        print("="*60)
        
        return conversation_id
        
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # 清理资源
        print("\n正在清理资源...")
        await service_manager.stop_service()
        print("清理完成")


async def main():
    """主函数"""
    # 确保使用 .env 文件
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    
    if not env_path.exists():
        print("❌ 错误：.env 文件不存在！")
        print(f"   期望位置: {env_path}")
        return
    
    print(f"加载环境配置: {env_path}")
    load_dotenv(env_path, override=True)
    
    # 验证关键API密钥
    required_keys = ['SILICONFLOW_API_KEY', 'GEMINI_API_KEY', 'OPENROUTER_API_KEY']
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    
    if missing_keys:
        print(f"❌ 错误：缺少必需的API密钥: {', '.join(missing_keys)}")
        print("   请在 .env 文件中配置这些密钥")
        return
    
    print("✅ API密钥验证通过")
    
    # 执行注入
    conversation_id = await inject_nebula_intelligence_memory()
    
    if conversation_id:
        print(f"\n🎉 测试准备完成！")
        print(f"   请在另一个项目窗口使用上述测试问题验证记忆功能。")


if __name__ == "__main__":
    asyncio.run(main())