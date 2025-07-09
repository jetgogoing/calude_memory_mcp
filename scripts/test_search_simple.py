#!/usr/bin/env python3
"""
简单的搜索测试 - 直接测试数据库和向量搜索
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.claude_memory.database.sync_session import get_sync_session
from src.claude_memory.models.data_models import MemoryUnitDB, ProjectDB
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

def test_database_search():
    """测试数据库中的数据"""
    print("=== 测试数据库搜索 ===\n")
    
    with get_sync_session() as session:
        # 1. 列出所有项目
        projects = session.query(ProjectDB).all()
        print("所有项目:")
        for p in projects:
            print(f"  - {p.id}: {p.name} (激活: {p.is_active})")
        
        # 2. 搜索包含"星云智能"的记忆单元
        print("\n搜索'星云智能'相关的记忆单元:")
        memories = session.query(MemoryUnitDB).filter(
            (MemoryUnitDB.title.contains("星云智能")) | 
            (MemoryUnitDB.summary.contains("星云智能")) |
            (MemoryUnitDB.content.contains("星云智能"))
        ).all()
        
        print(f"找到 {len(memories)} 条相关记忆:")
        for mem in memories:
            print(f"\n  记忆ID: {mem.id}")
            print(f"  项目: {mem.project_id}")
            print(f"  标题: {mem.title}")
            print(f"  摘要: {mem.summary[:100]}...")
            print(f"  关键词: {', '.join(mem.keywords[:5]) if mem.keywords else '无'}")

def test_qdrant_search():
    """测试Qdrant向量搜索"""
    print("\n\n=== 测试Qdrant向量搜索 ===\n")
    
    try:
        # 连接Qdrant
        client = QdrantClient(host="localhost", port=6333)
        
        # 检查集合
        collections = client.get_collections().collections
        print("Qdrant集合:")
        for col in collections:
            print(f"  - {col.name}: {col.points_count} 个向量")
        
        # 搜索"星云智能"
        from src.claude_memory.llm.embeddings import get_embedding_manager
        from src.claude_memory.config.settings import get_settings
        
        settings = get_settings()
        embedding_manager = get_embedding_manager()
        
        # 生成查询向量
        query_text = "星云智能 AI产品"
        query_vector = embedding_manager.embed_text_sync(query_text)
        
        # 在不同项目中搜索
        for project_id in ["nebula_test", "default", "shenrui_investment"]:
            print(f"\n在项目 '{project_id}' 中搜索:")
            
            # 构建过滤器
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="project_id",
                        match=MatchValue(value=project_id)
                    )
                ]
            )
            
            # 执行搜索
            results = client.search(
                collection_name=settings.vector.collection_name,
                query_vector=query_vector,
                query_filter=filter_condition,
                limit=3,
                with_payload=True
            )
            
            if results:
                print(f"  找到 {len(results)} 条结果:")
                for i, hit in enumerate(results, 1):
                    print(f"    {i}. 分数: {hit.score:.3f}")
                    if hit.payload:
                        print(f"       标题: {hit.payload.get('title', 'N/A')}")
                        print(f"       项目: {hit.payload.get('project_id', 'N/A')}")
            else:
                print("  没有找到结果")
                
    except Exception as e:
        print(f"Qdrant搜索错误: {str(e)}")

def main():
    """主函数"""
    test_database_search()
    test_qdrant_search()

if __name__ == "__main__":
    main()