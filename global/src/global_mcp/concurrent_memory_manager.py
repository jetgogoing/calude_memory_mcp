"""
Claude Memory 并发优化记忆管理器
支持高并发访问、连接池管理、缓存优化和异步处理
"""

import asyncio
import sqlite3
import aiosqlite
import json
import hashlib
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
from contextlib import asynccontextmanager
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
import weakref

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: float
    hit_count: int = 0
    
    def is_expired(self, ttl: float) -> bool:
        return time.time() - self.timestamp > ttl


class ConnectionPool:
    """SQLite连接池管理器"""
    
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)
        self._total_connections = 0
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger("connection_pool")
        
    async def initialize(self):
        """初始化连接池"""
        for _ in range(min(3, self.max_connections)):  # 预创建3个连接
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL")  # 启用WAL模式支持并发
            await conn.execute("PRAGMA synchronous=NORMAL")  # 优化同步模式
            await conn.execute("PRAGMA cache_size=10000")  # 增加缓存大小
            await conn.execute("PRAGMA temp_store=memory")  # 临时存储使用内存
            await self._pool.put(conn)
            self._total_connections += 1
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接"""
        conn = None
        try:
            # 尝试从池中获取连接
            try:
                conn = await asyncio.wait_for(self._pool.get(), timeout=5.0)
            except asyncio.TimeoutError:
                # 如果池中没有连接且未达到最大连接数，创建新连接
                async with self._lock:
                    if self._total_connections < self.max_connections:
                        conn = await aiosqlite.connect(self.db_path)
                        await conn.execute("PRAGMA journal_mode=WAL")
                        await conn.execute("PRAGMA synchronous=NORMAL")
                        await conn.execute("PRAGMA cache_size=10000")
                        await conn.execute("PRAGMA temp_store=memory")
                        self._total_connections += 1
                        self.logger.info(f"创建新连接，当前连接数: {self._total_connections}")
                    else:
                        # 等待连接可用
                        conn = await self._pool.get()
            
            yield conn
            
        finally:
            if conn:
                try:
                    await self._pool.put(conn)
                except:
                    # 如果放回连接池失败，关闭连接
                    await conn.close()
                    async with self._lock:
                        self._total_connections -= 1
    
    async def close_all(self):
        """关闭所有连接"""
        while not self._pool.empty():
            conn = await self._pool.get()
            await conn.close()
        self._total_connections = 0


class MemoryCache:
    """内存缓存管理器"""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired(self.default_ttl):
                    entry.hit_count += 1
                    self._stats["hits"] += 1
                    return entry.data
                else:
                    del self._cache[key]
            
            self._stats["misses"] += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值"""
        async with self._lock:
            # 如果缓存已满，移除最少使用的条目
            if len(self._cache) >= self.max_size and key not in self._cache:
                await self._evict_lru()
            
            self._cache[key] = CacheEntry(
                data=value,
                timestamp=time.time(),
                hit_count=0
            )
    
    async def _evict_lru(self):
        """移除最少使用的条目"""
        if not self._cache:
            return
        
        # 找到命中次数最少且最旧的条目
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].hit_count, self._cache[k].timestamp)
        )
        del self._cache[lru_key]
        self._stats["evictions"] += 1
    
    async def clear_expired(self):
        """清理过期条目"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired(self.default_ttl)
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            **self._stats,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache),
            "max_size": self.max_size
        }


class ConcurrentMemoryManager:
    """并发优化的全局记忆管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("concurrent_memory_manager")
        
        # 数据库配置
        self.db_url = config["database"]["url"]
        self.db_path = None
        if self.db_url.startswith("sqlite"):
            self.db_path = self.db_url.replace("sqlite:///", "")
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 并发配置
        concurrency_config = config.get("concurrency", {})
        self.max_connections = concurrency_config.get("max_connections", 10)
        self.cache_size = concurrency_config.get("cache_size", 1000)
        self.cache_ttl = concurrency_config.get("cache_ttl", 300.0)
        self.max_workers = concurrency_config.get("max_workers", 4)
        
        # 初始化组件
        self.connection_pool = ConnectionPool(self.db_path, self.max_connections)
        self.memory_cache = MemoryCache(self.cache_size, self.cache_ttl)
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # 读写锁
        self._read_locks = defaultdict(asyncio.Semaphore)
        self._write_locks = defaultdict(asyncio.Lock)
        
        # 批处理队ues
        self._batch_queue = asyncio.Queue()
        self._batch_task = None
        
        # 向量数据库配置
        self.vector_config = config.get("vector_store", {})
        self.qdrant_client = None
        if QDRANT_AVAILABLE and self.vector_config:
            try:
                self.qdrant_client = QdrantClient(url=self.vector_config["url"])
            except Exception as e:
                self.logger.warning(f"Qdrant连接失败: {e}")
        
        # 统计信息
        self._stats = {
            "total_requests": 0,
            "concurrent_requests": 0,
            "max_concurrent": 0,
            "avg_response_time": 0.0,
            "error_count": 0
        }
        self._current_requests = 0
        self._stats_lock = asyncio.Lock()
        
    async def initialize(self):
        """初始化管理器"""
        await self.connection_pool.initialize()
        await self._init_database()
        self._batch_task = asyncio.create_task(self._batch_processor())
        self.logger.info("并发记忆管理器初始化完成")
    
    async def _init_database(self):
        """初始化数据库表结构"""
        async with self.connection_pool.get_connection() as conn:
            # 全局对话表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS global_conversations (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    project_type TEXT DEFAULT 'unknown',
                    claude_thread_id TEXT,
                    global_conversation_id TEXT UNIQUE,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # 全局消息表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS global_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    global_message_id TEXT UNIQUE,
                    message_type TEXT DEFAULT 'user',
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT,
                    project_context TEXT DEFAULT '{}',
                    message_metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    has_code BOOLEAN DEFAULT FALSE,
                    code_language TEXT,
                    file_references TEXT DEFAULT '[]',
                    FOREIGN KEY (conversation_id) REFERENCES global_conversations (id)
                )
            """)
            
            # 创建索引优化查询性能
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_project ON global_conversations (project_name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created ON global_conversations (created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON global_messages (conversation_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_content ON global_messages (content)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON global_messages (created_at)")
            
            await conn.commit()
    
    async def _record_request_start(self):
        """记录请求开始"""
        async with self._stats_lock:
            self._current_requests += 1
            self._stats["concurrent_requests"] = self._current_requests
            self._stats["total_requests"] += 1
            if self._current_requests > self._stats["max_concurrent"]:
                self._stats["max_concurrent"] = self._current_requests
    
    async def _record_request_end(self, duration: float, success: bool):
        """记录请求结束"""
        async with self._stats_lock:
            self._current_requests -= 1
            self._stats["concurrent_requests"] = self._current_requests
            
            # 更新平均响应时间
            total = self._stats["total_requests"]
            current_avg = self._stats["avg_response_time"]
            self._stats["avg_response_time"] = ((current_avg * (total - 1)) + duration) / total
            
            if not success:
                self._stats["error_count"] += 1
    
    async def search_memories_concurrent(
        self, 
        query: str, 
        limit: int = 10,
        project_filter: Optional[str] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """并发优化的记忆搜索"""
        start_time = time.time()
        await self._record_request_start()
        
        try:
            # 生成缓存键
            cache_key = f"search:{hashlib.md5(f'{query}:{limit}:{project_filter}'.encode()).hexdigest()}"
            
            # 尝试从缓存获取
            if use_cache:
                cached_result = await self.memory_cache.get(cache_key)
                if cached_result is not None:
                    self.logger.debug(f"缓存命中: {cache_key}")
                    return cached_result
            
            # 数据库查询
            async with self.connection_pool.get_connection() as conn:
                if project_filter:
                    query_sql = """
                        SELECT DISTINCT
                            gm.content,
                            gm.role,
                            gm.message_type,
                            gc.project_name,
                            gc.project_path,
                            gc.title as conversation_title,
                            gm.created_at,
                            gc.id as conversation_id
                        FROM global_messages gm
                        JOIN global_conversations gc ON gm.conversation_id = gc.id
                        WHERE gc.project_name = ? AND gm.content LIKE ?
                        ORDER BY gm.created_at DESC
                        LIMIT ?
                    """
                    params = (project_filter, f"%{query}%", limit)
                else:
                    query_sql = """
                        SELECT DISTINCT
                            gm.content,
                            gm.role,
                            gm.message_type,
                            gc.project_name,
                            gc.project_path,
                            gc.title as conversation_title,
                            gm.created_at,
                            gc.id as conversation_id
                        FROM global_messages gm
                        JOIN global_conversations gc ON gm.conversation_id = gc.id
                        WHERE gm.content LIKE ?
                        ORDER BY gm.created_at DESC
                        LIMIT ?
                    """
                    params = (f"%{query}%", limit)
                
                async with conn.execute(query_sql, params) as cursor:
                    rows = await cursor.fetchall()
                
                results = [
                    {
                        "content": row[0],
                        "role": row[1],
                        "message_type": row[2],
                        "project_name": row[3],
                        "project_path": row[4],
                        "conversation_title": row[5],
                        "created_at": row[6],
                        "conversation_id": row[7]
                    }
                    for row in rows
                ]
            
            # 缓存结果
            if use_cache:
                await self.memory_cache.set(cache_key, results)
            
            duration = time.time() - start_time
            await self._record_request_end(duration, True)
            
            return results
            
        except Exception as e:
            duration = time.time() - start_time
            await self._record_request_end(duration, False)
            self.logger.error(f"搜索失败: {e}")
            raise
    
    async def get_recent_conversations_concurrent(
        self, 
        limit: int = 10,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """并发优化的最近对话获取"""
        start_time = time.time()
        await self._record_request_start()
        
        try:
            cache_key = f"recent_conversations:{limit}"
            
            if use_cache:
                cached_result = await self.memory_cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
            
            async with self.connection_pool.get_connection() as conn:
                query_sql = """
                    SELECT 
                        gc.id,
                        gc.title,
                        gc.project_name,
                        gc.project_path,
                        gc.created_at,
                        gc.last_activity,
                        gc.message_count,
                        (SELECT gm.content 
                         FROM global_messages gm 
                         WHERE gm.conversation_id = gc.id 
                         ORDER BY gm.created_at DESC 
                         LIMIT 1) as last_message
                    FROM global_conversations gc
                    ORDER BY gc.last_activity DESC
                    LIMIT ?
                """
                
                async with conn.execute(query_sql, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                
                results = [
                    {
                        "conversation_id": row[0],
                        "title": row[1],
                        "project_name": row[2],
                        "project_path": row[3],
                        "created_at": row[4],
                        "last_activity": row[5],
                        "message_count": row[6],
                        "last_message": row[7]
                    }
                    for row in rows
                ]
            
            if use_cache:
                await self.memory_cache.set(cache_key, results, ttl=60.0)  # 短期缓存
            
            duration = time.time() - start_time
            await self._record_request_end(duration, True)
            
            return results
            
        except Exception as e:
            duration = time.time() - start_time
            await self._record_request_end(duration, False)
            self.logger.error(f"获取最近对话失败: {e}")
            raise
    
    async def store_conversation_batch(
        self, 
        conversations: List[Tuple[Dict[str, Any], Dict[str, str]]]
    ) -> List[str]:
        """批量存储对话（并发优化）"""
        start_time = time.time()
        await self._record_request_start()
        
        try:
            conversation_ids = []
            
            async with self.connection_pool.get_connection() as conn:
                async with conn.execute("BEGIN") as _:
                    for conversation_data, project_context in conversations:
                        conversation_id = str(uuid.uuid4())
                        global_conversation_id = f"{project_context['project_name']}_{conversation_id}"
                        
                        # 插入对话
                        await conn.execute("""
                            INSERT INTO global_conversations (
                                id, project_path, project_name, project_type,
                                global_conversation_id, title, created_at, 
                                last_activity, metadata
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            conversation_id,
                            project_context["project_path"],
                            project_context["project_name"],
                            project_context.get("project_type", "unknown"),
                            global_conversation_id,
                            conversation_data.get("title", "Untitled Conversation"),
                            datetime.now().isoformat(),
                            datetime.now().isoformat(),
                            json.dumps(conversation_data.get("metadata", {}))
                        ))
                        
                        # 批量插入消息
                        messages = conversation_data.get("messages", [])
                        for message in messages:
                            message_id = str(uuid.uuid4())
                            global_message_id = f"{global_conversation_id}_{message_id}"
                            content_hash = hashlib.md5(message.get("content", "").encode()).hexdigest()
                            
                            await conn.execute("""
                                INSERT INTO global_messages (
                                    id, conversation_id, global_message_id, message_type,
                                    role, content, content_hash, project_context,
                                    message_metadata, created_at, has_code, code_language,
                                    file_references
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                message_id,
                                conversation_id,
                                global_message_id,
                                message.get("type", "user"),
                                message.get("role", "user"),
                                message.get("content", ""),
                                content_hash,
                                json.dumps(project_context),
                                json.dumps(message.get("metadata", {})),
                                datetime.now().isoformat(),
                                False,  # 简化版本，不做代码检测
                                None,
                                json.dumps([])
                            ))
                        
                        # 更新消息计数
                        await conn.execute("""
                            UPDATE global_conversations 
                            SET message_count = ? 
                            WHERE id = ?
                        """, (len(messages), conversation_id))
                        
                        conversation_ids.append(conversation_id)
                
                await conn.commit()
            
            # 清理相关缓存
            await self.memory_cache.clear_expired()
            
            duration = time.time() - start_time
            await self._record_request_end(duration, True)
            
            self.logger.info(f"批量存储 {len(conversations)} 个对话成功")
            return conversation_ids
            
        except Exception as e:
            duration = time.time() - start_time
            await self._record_request_end(duration, False)
            self.logger.error(f"批量存储对话失败: {e}")
            raise
    
    async def _batch_processor(self):
        """批处理任务处理器"""
        batch_size = 10
        batch_timeout = 5.0
        
        while True:
            try:
                batch = []
                deadline = time.time() + batch_timeout
                
                # 收集批处理任务
                while len(batch) < batch_size and time.time() < deadline:
                    try:
                        task = await asyncio.wait_for(
                            self._batch_queue.get(), 
                            timeout=deadline - time.time()
                        )
                        batch.append(task)
                    except asyncio.TimeoutError:
                        break
                
                # 处理批次
                if batch:
                    await self._process_batch(batch)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"批处理器错误: {e}")
                await asyncio.sleep(1)
    
    async def _process_batch(self, batch):
        """处理批处理任务"""
        # 这里可以实现具体的批处理逻辑
        # 例如批量写入、批量更新等
        self.logger.debug(f"处理批次: {len(batch)} 个任务")
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        cache_stats = self.memory_cache.get_stats()
        
        return {
            "concurrent_stats": dict(self._stats),
            "cache_stats": cache_stats,
            "connection_pool": {
                "total_connections": self.connection_pool._total_connections,
                "max_connections": self.connection_pool.max_connections,
                "queue_size": self.connection_pool._pool.qsize()
            },
            "batch_queue_size": self._batch_queue.qsize()
        }
    
    async def health_check_concurrent(self) -> Dict[str, Any]:
        """并发健康检查"""
        health_info = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }
        
        try:
            # 数据库连接检查
            async with self.connection_pool.get_connection() as conn:
                await conn.execute("SELECT 1")
                health_info["checks"]["database"] = {"status": "ok"}
        except Exception as e:
            health_info["checks"]["database"] = {"status": "error", "error": str(e)}
            health_info["status"] = "degraded"
        
        # 缓存检查
        try:
            await self.memory_cache.set("health_check", "ok", ttl=1.0)
            cached_value = await self.memory_cache.get("health_check")
            if cached_value == "ok":
                health_info["checks"]["cache"] = {"status": "ok"}
            else:
                health_info["checks"]["cache"] = {"status": "error", "error": "cache_mismatch"}
        except Exception as e:
            health_info["checks"]["cache"] = {"status": "error", "error": str(e)}
        
        # 性能指标
        health_info["performance"] = await self.get_performance_stats()
        
        return health_info
    
    async def close(self):
        """关闭管理器"""
        if self._batch_task:
            self._batch_task.cancel()
        
        await self.connection_pool.close_all()
        
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        
        self.logger.info("并发记忆管理器已关闭")


# 工厂函数
def create_concurrent_manager(config: Dict[str, Any]) -> ConcurrentMemoryManager:
    """创建并发记忆管理器实例"""
    return ConcurrentMemoryManager(config)