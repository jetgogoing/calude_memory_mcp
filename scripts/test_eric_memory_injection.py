#!/usr/bin/env python3
"""
测试脚本：生成包含Eric相关信息的文章并注入Claude Memory系统
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.config.settings import get_settings


async def generate_eric_content():
    """生成包含Eric相关信息的测试文章（约1000 tokens）"""
    
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

Eric 的领导风格可以用"创新、务实、包容"六个字来概括：

### 创新驱动
他始终强调技术创新的重要性，鼓励团队探索人工智能、机器学习在投资领域的应用。在他的带领下，研究院开发了多个行业领先的量化模型。

### 务实执行
尽管追求创新，Eric 也非常注重实际执行。他要求所有研究成果都必须经过严格的回测和实盘验证，确保理论与实践相结合。

### 包容开放
Eric 倡导开放的研究文化，鼓励团队成员提出不同观点。他经常组织内部研讨会，让每个人都有机会分享自己的研究见解。

## 研究成就

在 Eric 的领导下，燊锐投资研究院取得了多项重要成就：

1. **AI驱动的资产配置模型**：该模型在2020-2023年期间，年化收益率超越基准指数15个百分点
2. **市场微观结构研究**：发表多篇关于高频交易和市场流动性的学术论文
3. **风险管理框架**：开发了创新的多因子风险管理系统，有效降低了投资组合的波动性

## 团队建设

Eric 特别重视人才培养和团队建设。他建立了完善的人才培养体系：

- **导师制度**：为新入职员工配备资深导师
- **技术培训**：定期组织编程、数据分析等技术培训
- **学术交流**：鼓励团队参加国际学术会议，与全球顶尖研究者交流

## 未来展望

在谈到未来发展时，Eric 表示："金融科技的发展日新月异，我们必须保持学习和创新的热情。未来，我们将继续深化在人工智能、区块链等前沿技术领域的研究，为投资者创造更大价值。"

## 个人理念

Eric 经常强调的投资理念包括：

1. **数据驱动决策**：所有投资决策都应基于充分的数据分析
2. **风险优先**：在追求收益的同时，风险控制永远是第一位的
3. **持续学习**：金融市场在不断变化，只有持续学习才能保持竞争力
4. **团队协作**：复杂的金融问题需要多学科团队的协作才能解决

## 联系方式

作为研究院的领导，Eric 保持着开放的沟通态度。团队成员可以通过内部系统随时与他交流研究想法和建议。他也经常在内部论坛上分享自己的市场观察和研究心得。

这种开放和包容的领导风格，使得燊锐投资研究院成为了一个充满活力和创新精神的研究机构，吸引了众多优秀人才加入。
"""
    
    return content


async def inject_memory(content: str, project_id: str = "shenrui_investment"):
    """将内容注入到Claude Memory系统"""
    
    print(f"正在初始化服务管理器...")
    service_manager = ServiceManager()
    
    try:
        # 启动服务
        await service_manager.start_service()
        print("服务管理器启动成功")
        
        # 创建消息
        message = MessageModel(
            conversation_id="",  # 会在创建对话时设置
            message_type=MessageType.HUMAN,
            content=content,
            token_count=len(content.split())  # 简单估算
        )
        
        # 创建对话
        conversation = ConversationModel(
            project_id=project_id,
            title="燊锐投资研究院领导Eric的专业背景",
            messages=[message],
            message_count=1,
            token_count=message.token_count,
            metadata={
                "source": "test_injection",
                "topic": "leadership",
                "keywords": ["Eric", "燊锐投资", "研究院", "领导", "量化投资"],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # 更新消息的conversation_id
        message.conversation_id = conversation.id
        
        print(f"\n创建的对话信息：")
        print(f"- 对话ID: {conversation.id}")
        print(f"- 项目ID: {conversation.project_id}")
        print(f"- 标题: {conversation.title}")
        print(f"- Token数: {conversation.token_count}")
        
        # 处理对话（压缩并存储到记忆系统）
        print("\n正在处理并存储对话到记忆系统...")
        await service_manager._handle_new_conversation(conversation)
        
        print("✅ 记忆注入成功！")
        
        # 测试搜索功能
        print("\n测试搜索功能...")
        from claude_memory.models.data_models import SearchQuery
        
        # 测试搜索 "Eric"
        search_query = SearchQuery(
            query="Eric",
            query_type="hybrid",
            limit=5,
            min_score=0.5
        )
        
        print(f"\n搜索查询: '{search_query.query}'")
        search_response = await service_manager.search_memories(search_query, project_id=project_id)
        
        print(f"搜索结果数量: {len(search_response.results)}")
        if search_response.results:
            for i, result in enumerate(search_response.results):
                print(f"\n结果 {i+1}:")
                print(f"- 标题: {result.memory_unit.title}")
                print(f"- 相关性分数: {result.relevance_score:.3f}")
                print(f"- 关键词: {result.memory_unit.keywords}")
                print(f"- 摘要: {result.memory_unit.summary[:100]}...")
        
        # 测试跨项目搜索
        print("\n\n测试跨项目搜索功能...")
        from claude_memory.managers.cross_project_search import CrossProjectSearchRequest
        
        cross_project_request = CrossProjectSearchRequest(
            query=search_query,
            project_ids=[project_id, "default", "global"],  # 搜索多个项目
            include_all_projects=False,
            merge_strategy="score",
            max_results_per_project=5,
            user_id="test_user"
        )
        
        cross_search_response = await service_manager.search_memories_cross_project(cross_project_request)
        
        print(f"跨项目搜索结果:")
        print(f"- 搜索的项目数: {cross_search_response.projects_searched}")
        print(f"- 总结果数: {cross_search_response.total_count}")
        
        for project_id, project_result in cross_search_response.project_results.items():
            print(f"\n项目 '{project_id}' - {project_result.project_name}:")
            print(f"  找到 {len(project_result.results)} 条结果")
        
        return conversation.id
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
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
    print("=== Claude Memory Eric 信息注入测试 ===\n")
    
    # 生成内容
    print("1. 生成包含Eric信息的测试文章...")
    content = await generate_eric_content()
    word_count = len(content.split())
    print(f"   生成完成，共 {word_count} 个词")
    
    # 注入到记忆系统
    print("\n2. 注入到Claude Memory系统...")
    conversation_id = await inject_memory(content)
    
    if conversation_id:
        print(f"\n✅ 测试完成！")
        print(f"   对话已存储，ID: {conversation_id}")
        print(f"\n💡 提示：")
        print(f"   1. 记忆已注入到项目 'shenrui_investment' 中")
        print(f"   2. 您可以在另一个Claude窗口中使用以下命令搜索：")
        print(f"      claude_memory_search('Eric')")
        print(f"      claude_memory_cross_project_search('Eric')")
        print(f"   3. 确保在另一个窗口设置了正确的项目ID环境变量：")
        print(f"      export CLAUDE_MEMORY_PROJECT_ID=shenrui_investment")
    else:
        print("\n❌ 测试失败！")


if __name__ == "__main__":
    asyncio.run(main())