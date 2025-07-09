
import asyncio
from qdrant_client import AsyncQdrantClient
import psycopg2

async def update_vector_payloads():
    # 连接数据库获取memory_units信息
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="claude_memory",
        user="claude_memory",
        password="password"
    )
    cursor = conn.cursor()
    
    # 获取所有memory_units
    cursor.execute("SELECT id, project_id FROM memory_units")
    units = cursor.fetchall()
    
    # 连接Qdrant
    client = AsyncQdrantClient(url="http://localhost:6333")
    
    # 批量更新payload
    for unit_id, project_id in units:
        try:
            # 获取现有点
            points = await client.retrieve(
                collection_name="claude_memory_vectors_v14",
                ids=[str(unit_id)]
            )
            
            if points:
                point = points[0]
                # 更新payload
                payload = point.payload or {}
                payload['project_id'] = project_id
                payload['memory_unit_id'] = str(unit_id)
                
                # 更新点
                await client.set_payload(
                    collection_name="claude_memory_vectors_v14",
                    payload=payload,
                    points=[str(unit_id)]
                )
                print(f"✅ Updated vector {unit_id}")
        except Exception as e:
            print(f"❌ Failed to update {unit_id}: {e}")
    
    cursor.close()
    conn.close()
    await client.close()

if __name__ == "__main__":
    asyncio.run(update_vector_payloads())
