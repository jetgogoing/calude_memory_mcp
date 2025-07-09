#!/usr/bin/env python3
"""
为测试数据创建向量
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from src.claude_memory.managers.service_manager import ServiceManager
from src.claude_memory.models.data_models import MemoryUnitModel, MemoryUnitType

async def create_test_vector():
    """创建测试向量"""
    print("🔧 为测试数据创建向量...")
    
    # 初始化ServiceManager
    service_manager = ServiceManager()
    await service_manager.start_service()
    
    try:
        # 创建MemoryUnitModel
        memory_unit = MemoryUnitModel(
            memory_id="test-updateresult-001",
            project_id="default",
            conversation_id="02177d43-864f-4a38-9d9e-f85abc800c40",
            unit_type=MemoryUnitType.CONVERSATION,
            title="UpdateResult错误讨论",
            summary="UpdateResult错误通常出现在异步编程中，特别是使用asyncio库时。这个错误表示一个协程或Future对象没有被正确等待或处理。",
            content="用户询问了什么是UpdateResult错误以及在什么情况下会出现。助手解释了这是异步编程中的常见错误，通常因为忘记使用await关键字、异步函数返回值处理不当或事件循环管理问题导致。解决方法是确保所有异步调用都被正确await，并检查异步上下文管理。",
            keywords=["UpdateResult错误", "asyncio", "异步编程", "协程", "await", "Future", "事件循环"],
            token_count=200,
            created_at=datetime.utcnow(),
            metadata={"test": True, "source": "manual_test"}
        )
        
        # 存储到向量数据库
        success = await service_manager.semantic_retriever.store_memory_unit(memory_unit)
        
        if success:
            print("✅ 测试向量创建成功!")
            
            # 验证向量存储
            from src.claude_memory.models.data_models import SearchQuery
            search_query = SearchQuery(
                query="UpdateResult错误",
                query_type="hybrid",
                limit=5,
                min_score=0.3
            )
            
            from src.claude_memory.retrievers.semantic_retriever import RetrievalRequest
            request = RetrievalRequest(
                query=search_query,
                project_id="default",
                limit=5,
                min_score=0.3
            )
            
            # 测试搜索
            results = await service_manager.semantic_retriever.retrieve_memories(request)
            print(f"📊 搜索测试: 找到 {len(results.results)} 条结果")
            
            for i, result in enumerate(results.results):
                print(f"  [{i+1}] {result.memory_unit.title} (分数: {result.relevance_score:.3f})")
        else:
            print("❌ 测试向量创建失败")
            
    finally:
        await service_manager.stop_service()

if __name__ == "__main__":
    asyncio.run(create_test_vector())