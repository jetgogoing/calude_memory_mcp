#!/usr/bin/env python3
"""
检查 PostgreSQL 和 Qdrant 数据同步问题
找出哪些记忆单元没有被向量化
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extras import RealDictCursor
from qdrant_client import QdrantClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def check_data_sync():
    """检查数据同步状态"""
    print("检查数据同步状态")
    print("=" * 60)
    
    # 数据库连接
    db_url = os.getenv("DATABASE_URL", "postgresql://claude_memory:password@localhost:5433/claude_memory")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection_name = os.getenv("QDRANT_COLLECTION_NAME", "claude_memory_vectors_v14")
    
    try:
        # 连接 PostgreSQL
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 获取所有记忆单元
        cursor.execute("""
            SELECT id, conversation_id, unit_type, title, created_at, is_active
            FROM memory_units
            ORDER BY created_at DESC
        """)
        memory_units = cursor.fetchall()
        print(f"\nPostgreSQL 中的记忆单元总数: {len(memory_units)}")
        
        # 获取所有嵌入记录
        cursor.execute("""
            SELECT memory_unit_id, model_name, dimension, created_at
            FROM embeddings
        """)
        embeddings = cursor.fetchall()
        embedding_ids = {str(e['memory_unit_id']) for e in embeddings}
        print(f"PostgreSQL 中的嵌入向量总数: {len(embeddings)}")
        
        # 连接 Qdrant
        client = QdrantClient(url=qdrant_url)
        
        # 获取 Qdrant 中的所有向量
        qdrant_points = []
        offset = None
        while True:
            response = client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            points, next_offset = response
            qdrant_points.extend(points)
            if next_offset is None:
                break
            offset = next_offset
        
        qdrant_ids = {point.id for point in qdrant_points}
        print(f"Qdrant 中的向量总数: {len(qdrant_ids)}")
        
        # 分析数据同步问题
        print("\n" + "=" * 60)
        print("数据同步分析:")
        
        # 找出没有嵌入向量的记忆单元
        units_without_embedding = []
        for unit in memory_units:
            unit_id = str(unit['id'])
            if unit_id not in embedding_ids:
                units_without_embedding.append(unit)
        
        if units_without_embedding:
            print(f"\n未生成嵌入向量的记忆单元 ({len(units_without_embedding)} 个):")
            for unit in units_without_embedding[:10]:  # 只显示前10个
                print(f"  - ID: {unit['id']}")
                print(f"    标题: {unit['title']}")
                print(f"    类型: {unit['unit_type']}")
                print(f"    创建时间: {unit['created_at']}")
                print(f"    是否活跃: {unit['is_active']}")
                print()
        
        # 找出没有存储到 Qdrant 的嵌入向量
        embeddings_not_in_qdrant = []
        for embed in embeddings:
            embed_id = str(embed['memory_unit_id'])
            if embed_id not in qdrant_ids:
                embeddings_not_in_qdrant.append(embed)
        
        if embeddings_not_in_qdrant:
            print(f"\n已生成但未存储到 Qdrant 的嵌入向量 ({len(embeddings_not_in_qdrant)} 个):")
            for embed in embeddings_not_in_qdrant:
                print(f"  - Memory Unit ID: {embed['memory_unit_id']}")
                print(f"    模型: {embed['model_name']}")
                print(f"    维度: {embed['dimension']}")
                print(f"    创建时间: {embed['created_at']}")
                print()
        
        # 找出 Qdrant 中存在但 PostgreSQL 中不存在的向量
        qdrant_only_ids = qdrant_ids - embedding_ids
        if qdrant_only_ids:
            print(f"\n仅存在于 Qdrant 中的向量 ({len(qdrant_only_ids)} 个):")
            for point_id in list(qdrant_only_ids)[:5]:  # 只显示前5个
                print(f"  - ID: {point_id}")
        
        # 统计总结
        print("\n" + "=" * 60)
        print("同步状态总结:")
        print(f"- 总记忆单元数: {len(memory_units)}")
        print(f"- 已生成嵌入向量: {len(embeddings)}")
        print(f"- 已存储到 Qdrant: {len(qdrant_ids)}")
        print(f"- 缺失嵌入向量: {len(units_without_embedding)}")
        print(f"- 缺失 Qdrant 存储: {len(embeddings_not_in_qdrant)}")
        print(f"- 数据一致性: {'✗ 不一致' if units_without_embedding or embeddings_not_in_qdrant else '✓ 一致'}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"检查过程中出错: {e}")
        import traceback
        traceback.print_exc()


def check_conversation_details():
    """检查对话详情"""
    print("\n\n" + "=" * 60)
    print("对话详情分析:")
    
    db_url = os.getenv("DATABASE_URL", "postgresql://claude_memory:password@localhost:5433/claude_memory")
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 获取所有对话及其记忆单元
        cursor.execute("""
            SELECT 
                c.id as conv_id,
                c.title,
                c.message_count,
                c.token_count,
                c.created_at,
                COUNT(mu.id) as memory_unit_count
            FROM conversations c
            LEFT JOIN memory_units mu ON mu.conversation_id = c.id
            GROUP BY c.id, c.title, c.message_count, c.token_count, c.created_at
            ORDER BY c.created_at DESC
        """)
        
        conversations = cursor.fetchall()
        
        print(f"\n对话总数: {len(conversations)}")
        print("\n对话列表:")
        
        no_memory_convs = []
        for conv in conversations:
            status = "✓" if conv['memory_unit_count'] > 0 else "✗"
            print(f"{status} {conv['title']} ({conv['created_at'].strftime('%Y-%m-%d %H:%M')})")
            print(f"  - 消息数: {conv['message_count']}, Token数: {conv['token_count']}")
            print(f"  - 记忆单元数: {conv['memory_unit_count']}")
            
            if conv['memory_unit_count'] == 0:
                no_memory_convs.append(conv)
        
        if no_memory_convs:
            print(f"\n警告: {len(no_memory_convs)} 个对话没有生成记忆单元!")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"检查对话详情时出错: {e}")


if __name__ == "__main__":
    check_data_sync()
    check_conversation_details()