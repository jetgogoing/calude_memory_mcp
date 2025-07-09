#!/usr/bin/env python3
"""
检查Qdrant向量数据库
"""

import asyncio
import sys
sys.path.insert(0, '/home/jetgogoing/claude_memory/src')

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

async def check_qdrant():
    """检查Qdrant向量数据库"""
    
    # 创建客户端
    client = AsyncQdrantClient(host="localhost", port=6333)
    
    try:
        # 检查集合
        collections = await client.get_collections()
        print(f"=== Qdrant集合总数: {len(collections.collections)} ===")
        
        for collection in collections.collections:
            print(f"\n集合: {collection.name}")
            
            # 获取集合信息
            collection_info = await client.get_collection(collection.name)
            print(f"  向量数量: {collection_info.vectors_count}")
            print(f"  向量维度: {collection_info.config.params.vectors.size}")
            
            # 搜索所有向量
            search_result = await client.scroll(
                collection_name=collection.name,
                limit=10,
                with_payload=True
            )
            
            print(f"  实际向量数量: {len(search_result[0])}")
            
            # 显示前几个向量的元数据
            if search_result[0]:
                print("  前几个向量的元数据:")
                for i, point in enumerate(search_result[0][:5]):
                    print(f"    {i+1}. ID: {point.id}")
                    if point.payload:
                        print(f"       标题: {point.payload.get('title', 'N/A')}")
                        print(f"       类型: {point.payload.get('unit_type', 'N/A')}")
                        print(f"       创建时间: {point.payload.get('created_at', 'N/A')}")
                        
        # 测试搜索"星云智能"
        print("\n=== 测试搜索'星云智能' ===")
        for collection in collections.collections:
            # 先尝试滚动查找包含"星云智能"的记录
            scroll_result = await client.scroll(
                collection_name=collection.name,
                limit=100,
                with_payload=True
            )
            
            nebula_points = []
            for point in scroll_result[0]:
                if point.payload and any(
                    "星云智能" in str(value) for value in point.payload.values()
                ):
                    nebula_points.append(point)
            
            print(f"集合 {collection.name} 中包含'星云智能'的记录数: {len(nebula_points)}")
            
            for point in nebula_points:
                print(f"  - ID: {point.id}")
                print(f"    标题: {point.payload.get('title', 'N/A')}")
                print(f"    摘要: {point.payload.get('summary', 'N/A')[:50]}...")
                
    except Exception as e:
        print(f"❌ 检查Qdrant失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check_qdrant())