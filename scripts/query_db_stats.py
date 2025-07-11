#!/usr/bin/env python3
"""
查询 PostgreSQL 和 Qdrant 数据库中的聊天记录统计
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extras import RealDictCursor
from qdrant_client import QdrantClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def query_postgresql_stats():
    """查询 PostgreSQL 数据库统计信息"""
    print("\n=== PostgreSQL 数据库统计 ===")
    
    # 从环境变量获取数据库连接信息
    db_url = os.getenv("DATABASE_URL", "postgresql://claude_memory:password@localhost:5433/claude_memory")
    
    try:
        # 连接数据库
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 查询对话总数
        cursor.execute("SELECT COUNT(*) as count FROM conversations")
        conversations_count = cursor.fetchone()['count']
        print(f"对话总数: {conversations_count}")
        
        # 查询消息总数
        cursor.execute("SELECT COUNT(*) as count FROM messages")
        messages_count = cursor.fetchone()['count']
        print(f"消息总数: {messages_count}")
        
        # 查询记忆单元总数
        cursor.execute("SELECT COUNT(*) as count FROM memory_units")
        memory_units_count = cursor.fetchone()['count']
        print(f"记忆单元总数: {memory_units_count}")
        
        # 按类型统计记忆单元
        cursor.execute("""
            SELECT unit_type, COUNT(*) as count 
            FROM memory_units 
            GROUP BY unit_type 
            ORDER BY count DESC
        """)
        print("\n记忆单元类型分布:")
        for row in cursor.fetchall():
            print(f"  {row['unit_type']}: {row['count']}")
        
        # 查询嵌入向量总数
        cursor.execute("SELECT COUNT(*) as count FROM embeddings")
        embeddings_count = cursor.fetchone()['count']
        print(f"\n嵌入向量总数: {embeddings_count}")
        
        # 查询成本追踪记录数
        cursor.execute("SELECT COUNT(*) as count FROM cost_tracking")
        cost_tracking_count = cursor.fetchone()['count']
        print(f"成本追踪记录数: {cost_tracking_count}")
        
        # 查询最近的对话
        cursor.execute("""
            SELECT id, title, started_at, message_count, token_count 
            FROM conversations 
            ORDER BY started_at DESC 
            LIMIT 5
        """)
        recent_conversations = cursor.fetchall()
        print("\n最近的5个对话:")
        for conv in recent_conversations:
            print(f"  - {conv['title'] or '未命名对话'} ({conv['started_at'].strftime('%Y-%m-%d %H:%M:%S')})")
            print(f"    消息数: {conv['message_count']}, Token数: {conv['token_count']}")
        
        # 统计总 token 使用量
        cursor.execute("SELECT SUM(token_count) as total_tokens FROM conversations")
        total_tokens = cursor.fetchone()['total_tokens'] or 0
        print(f"\n总 Token 使用量: {total_tokens:,}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"查询 PostgreSQL 时出错: {e}")


def query_qdrant_stats():
    """查询 Qdrant 向量数据库统计信息"""
    print("\n\n=== Qdrant 向量数据库统计 ===")
    
    # 从环境变量获取 Qdrant 连接信息
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection_name = os.getenv("QDRANT_COLLECTION_NAME", "claude_memory_vectors_v14")
    
    try:
        # 连接 Qdrant
        client = QdrantClient(url=qdrant_url)
        
        # 获取集合信息
        collections = client.get_collections().collections
        print(f"集合总数: {len(collections)}")
        
        # 查看目标集合是否存在
        collection_exists = any(col.name == collection_name for col in collections)
        
        if collection_exists:
            # 获取集合详细信息
            collection_info = client.get_collection(collection_name)
            print(f"\n集合 '{collection_name}' 信息:")
            print(f"  向量数量: {collection_info.points_count}")
            print(f"  向量维度: {collection_info.config.params.vectors.size}")
            print(f"  距离度量: {collection_info.config.params.vectors.distance}")
            
            # 获取一些示例向量
            if collection_info.points_count > 0:
                sample_points = client.scroll(
                    collection_name=collection_name,
                    limit=5,
                    with_payload=True,
                    with_vectors=False
                )
                
                print(f"\n最近的5个向量记录:")
                for point in sample_points[0]:
                    payload = point.payload
                    print(f"  - ID: {point.id}")
                    if 'title' in payload:
                        print(f"    标题: {payload.get('title', 'N/A')}")
                    if 'created_at' in payload:
                        print(f"    创建时间: {payload.get('created_at', 'N/A')}")
        else:
            print(f"\n集合 '{collection_name}' 不存在")
            
        # 列出所有集合
        print("\n所有集合:")
        for col in collections:
            print(f"  - {col.name}")
            
    except Exception as e:
        print(f"查询 Qdrant 时出错: {e}")


def main():
    """主函数"""
    print("Claude Memory 数据库统计报告")
    print("=" * 50)
    print(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 查询 PostgreSQL
    query_postgresql_stats()
    
    # 查询 Qdrant
    query_qdrant_stats()
    
    print("\n" + "=" * 50)
    print("查询完成")


if __name__ == "__main__":
    main()