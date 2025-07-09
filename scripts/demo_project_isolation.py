#!/usr/bin/env python3
"""
Claude Memory MCP Service - 项目隔离演示

演示如何使用项目ID实现记忆隔离。
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from claude_memory.managers.project_manager import get_project_manager
from claude_memory.models.data_models import (
    ConversationModel,
    MessageModel,
    MessageType,
    SearchQuery,
)
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.processors.semantic_compressor import CompressionRequest, MemoryUnitType


async def demo_project_isolation():
    """演示项目隔离功能"""
    print("🚀 Claude Memory - 项目隔离演示")
    print("=" * 60)
    
    # 初始化管理器
    project_manager = get_project_manager()
    service_manager = ServiceManager()
    
    try:
        await service_manager.start_service()
        print("✅ 服务初始化成功")
        
        # 创建演示项目
        print("\n📁 创建演示项目...")
        
        project_web = project_manager.create_project(
            project_id="web_development",
            name="Web开发项目",
            description="前端和后端开发相关的记忆"
        )
        print(f"  ✓ 创建项目: {project_web.name} (ID: {project_web.id})")
        
        project_ml = project_manager.create_project(
            project_id="machine_learning",
            name="机器学习项目",
            description="AI和机器学习相关的记忆"
        )
        print(f"  ✓ 创建项目: {project_ml.name} (ID: {project_ml.id})")
        
        # 为Web项目添加对话记忆
        print("\n💬 添加项目特定的对话记忆...")
        
        web_conversation = ConversationModel(
            project_id="web_development",
            session_id="web_session_1",
            title="React组件开发讨论",
            messages=[
                MessageModel(
                    conversation_id="",
                    message_type=MessageType.HUMAN,
                    content="如何在React中实现自定义Hook来管理表单状态？",
                    timestamp=datetime.utcnow()
                ),
                MessageModel(
                    conversation_id="",
                    message_type=MessageType.ASSISTANT,
                    content="在React中创建自定义Hook管理表单状态是一个很好的实践。可以使用useState和useReducer来实现。",
                    timestamp=datetime.utcnow()
                )
            ],
            started_at=datetime.utcnow()
        )
        
        # 压缩并存储
        if service_manager.semantic_compressor:
            compression_request = CompressionRequest(
                conversation=web_conversation,
                unit_type=MemoryUnitType.QUICK_MU
            )
            result = await service_manager.semantic_compressor.compress_conversation(compression_request)
            print("  ✓ Web项目记忆已保存")
        
        # 为ML项目添加对话记忆
        ml_conversation = ConversationModel(
            project_id="machine_learning",
            session_id="ml_session_1",
            title="神经网络架构讨论",
            messages=[
                MessageModel(
                    conversation_id="",
                    message_type=MessageType.HUMAN,
                    content="如何选择合适的神经网络架构来处理图像分类任务？",
                    timestamp=datetime.utcnow()
                ),
                MessageModel(
                    conversation_id="",
                    message_type=MessageType.ASSISTANT,
                    content="对于图像分类任务，CNN（卷积神经网络）是首选。可以考虑ResNet、EfficientNet等预训练模型。",
                    timestamp=datetime.utcnow()
                )
            ],
            started_at=datetime.utcnow()
        )
        
        if service_manager.semantic_compressor:
            compression_request = CompressionRequest(
                conversation=ml_conversation,
                unit_type=MemoryUnitType.QUICK_MU
            )
            result = await service_manager.semantic_compressor.compress_conversation(compression_request)
            print("  ✓ ML项目记忆已保存")
        
        # 等待处理完成
        await asyncio.sleep(2)
        
        # 演示搜索隔离
        print("\n🔍 演示项目记忆隔离...")
        
        # 在Web项目中搜索"React"
        print("\n在Web开发项目中搜索 'React':")
        search_query = SearchQuery(query="React Hook", query_type="hybrid", limit=5)
        web_results = await service_manager.search_memories(search_query, project_id="web_development")
        print(f"  找到 {web_results.total_count} 条相关记忆")
        for i, result in enumerate(web_results.results[:3], 1):
            print(f"  {i}. {result.memory_unit.title} (相关度: {result.relevance_score:.2f})")
        
        # 在ML项目中搜索"React"
        print("\n在机器学习项目中搜索 'React':")
        ml_results = await service_manager.search_memories(search_query, project_id="machine_learning")
        print(f"  找到 {ml_results.total_count} 条相关记忆")
        if ml_results.total_count == 0:
            print("  ✓ 正确：ML项目中没有React相关的记忆")
        
        # 在ML项目中搜索"神经网络"
        print("\n在机器学习项目中搜索 '神经网络':")
        nn_query = SearchQuery(query="神经网络 CNN", query_type="hybrid", limit=5)
        nn_results = await service_manager.search_memories(nn_query, project_id="machine_learning")
        print(f"  找到 {nn_results.total_count} 条相关记忆")
        for i, result in enumerate(nn_results.results[:3], 1):
            print(f"  {i}. {result.memory_unit.title} (相关度: {result.relevance_score:.2f})")
        
        # 显示项目统计
        print("\n📊 项目统计信息:")
        projects = project_manager.list_projects()
        
        for project in projects:
            stats = project_manager.get_project_statistics(project.id)
            print(f"\n项目: {project.name} (ID: {project.id})")
            print(f"  - 对话数: {stats.get('conversation_count', 0)}")
            print(f"  - 记忆单元数: {stats.get('memory_unit_count', 0)}")
            print(f"  - 总Token数: {stats.get('total_tokens', 0)}")
        
        print("\n✅ 演示完成！")
        print("\n💡 总结:")
        print("  1. 不同项目的记忆是完全隔离的")
        print("  2. 搜索只会返回指定项目内的记忆")
        print("  3. 每个项目有独立的统计信息")
        print("  4. 支持软删除和硬删除项目")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理演示项目（可选）
        cleanup = input("\n是否清理演示项目？(y/N): ")
        if cleanup.lower() == 'y':
            print("\n🧹 清理演示项目...")
            project_manager.delete_project("web_development", soft_delete=False)
            project_manager.delete_project("machine_learning", soft_delete=False)
            print("  ✓ 演示项目已删除")
        
        await service_manager.stop_service()
        print("\n👋 再见！")


if __name__ == "__main__":
    asyncio.run(demo_project_isolation())