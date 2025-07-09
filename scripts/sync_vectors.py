#!/usr/bin/env python3
"""
同步PostgreSQL数据到Qdrant向量数据库
修复Phase 2搜索功能问题
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.models.data_models import MemoryUnitModel, MemoryUnitType
from claude_memory.config.settings import get_settings

async def sync_database_to_vectors():
    """同步数据库记录到向量数据库"""
    print("🔧 开始同步数据库到向量数据库...")
    print("=" * 60)
    
    # 数据库连接配置
    db_config = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5433")),
        "database": os.getenv("POSTGRES_DB", "claude_memory"),
        "user": os.getenv("POSTGRES_USER", "claude_memory"),
        "password": os.getenv("POSTGRES_PASSWORD", "password")
    }
    
    # 连接数据库
    conn = psycopg2.connect(**db_config, cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    
    try:
        # 获取所有需要同步的记录
        cursor.execute("""
            SELECT 
                id, project_id, conversation_id, unit_type,
                title, summary, content, keywords,
                relevance_score, token_count, created_at,
                updated_at, expires_at, metadata, is_active
            FROM memory_units
            WHERE project_id = 'default'
            ORDER BY created_at DESC
        """)
        
        records = cursor.fetchall()
        print(f"📊 找到 {len(records)} 条需要同步的记录")
        
        if not records:
            print("⚠️ 没有找到需要同步的记录")
            return
        
        # 初始化SemanticRetriever
        retriever = SemanticRetriever()
        # SemanticRetriever在__init__中已经初始化了
        
        # 统计
        success_count = 0
        failed_count = 0
        
        # 逐条同步
        for i, record in enumerate(records, 1):
            try:
                # 清理title字段中的JSON格式
                title = record['title']
                if title.startswith('```json'):
                    # 尝试提取实际标题
                    import re
                    match = re.search(r'"title"\s*:\s*"([^"]+)"', title)
                    if match:
                        title = match.group(1)
                    else:
                        title = f"记录_{record['id'][:8]}"
                
                # 创建MemoryUnitModel
                memory_unit = MemoryUnitModel(
                    memory_id=str(record['id']),
                    project_id=record['project_id'],
                    conversation_id=str(record['conversation_id']),
                    unit_type=record['unit_type'],
                    title=title,
                    summary=record['summary'],
                    content=record['content'],
                    keywords=record['keywords'] or [],
                    relevance_score=float(record['relevance_score']),
                    token_count=record['token_count'],
                    created_at=record['created_at'],
                    updated_at=record['updated_at'],
                    expires_at=record['expires_at'],
                    metadata=record['metadata'] or {},
                    is_active=record['is_active']
                )
                
                print(f"\n[{i}/{len(records)}] 处理: {title[:50]}...")
                
                # 存储到向量数据库
                success = await retriever.store_memory_unit(memory_unit)
                
                if success:
                    success_count += 1
                    print(f"  ✅ 成功同步向量")
                else:
                    failed_count += 1
                    print(f"  ❌ 同步失败")
                    
            except Exception as e:
                failed_count += 1
                print(f"  ❌ 处理失败: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # 输出统计
        print("\n" + "=" * 60)
        print(f"📊 同步完成统计:")
        print(f"  - 成功: {success_count}")
        print(f"  - 失败: {failed_count}")
        print(f"  - 成功率: {success_count/len(records)*100:.1f}%")
        
        # 验证向量数量
        await verify_vectors(retriever)
        
    finally:
        cursor.close()
        conn.close()
        print("\n✅ 数据库连接已关闭")

async def verify_vectors(retriever):
    """验证向量同步结果"""
    print("\n🔍 验证向量数据库...")
    
    # 使用Qdrant客户端检查
    from qdrant_client.http import models as qdrant_models
    
    try:
        # 计算default项目的向量数量
        count_result = await retriever.qdrant_client.count(
            collection_name=retriever.collection_name,
            count_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="project_id",
                        match=qdrant_models.MatchValue(value="default")
                    )
                ]
            )
        )
        
        print(f"✅ Qdrant中project_id='default'的向量数: {count_result.count}")
        
        # 测试搜索功能
        from claude_memory.models.data_models import SearchQuery
        from claude_memory.retrievers.semantic_retriever import RetrievalRequest
        
        test_queries = ["UpdateResult", "错误", "asyncio", "测试"]
        
        print("\n🧪 测试搜索功能:")
        for query_text in test_queries:
            search_query = SearchQuery(
                query=query_text,
                query_type="hybrid",
                limit=3,
                min_score=0.3
            )
            
            request = RetrievalRequest(
                query=search_query,
                project_id="default",
                limit=3,
                min_score=0.3
            )
            
            result = await retriever.retrieve_memories(request)
            print(f"  - 查询 '{query_text}': 找到 {len(result.results)} 条结果")
            
            if result.results:
                for r in result.results[:2]:
                    print(f"    • {r.memory_unit.title[:50]} (分数: {r.relevance_score:.3f})")
        
    except Exception as e:
        print(f"❌ 验证失败: {str(e)}")

if __name__ == "__main__":
    print("🚀 Claude Memory 向量同步工具")
    print("版本: 1.0.0")
    print("用途: 修复Phase 2搜索功能问题")
    print()
    
    # 运行同步
    asyncio.run(sync_database_to_vectors())