"""
Claude Memory 全局记忆管理器
支持跨项目记忆存储、检索和管理
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid
import logging

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

class GlobalMemoryManager:
    """全局记忆管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("global_memory_manager")
        
        # 数据库配置
        self.db_url = config["database"]["url"]
        self.db_path = None
        if self.db_url.startswith("sqlite"):
            self.db_path = self.db_url.replace("sqlite:///", "")
            # 确保数据库目录存在
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 向量数据库配置
        self.vector_config = config["vector_store"]
        self.qdrant_client = None
        if QDRANT_AVAILABLE:
            try:
                self.qdrant_client = QdrantClient(url=self.vector_config["url"])
            except Exception as e:
                self.logger.warning(f"Qdrant连接失败: {e}")
        
        # 初始化数据库
        self.init_database()
        self.init_vector_store()
    
    def init_database(self):
        """初始化SQLite数据库"""
        if not self.db_path:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建全局对话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_conversations (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    claude_thread_id TEXT,
                    global_conversation_id TEXT UNIQUE,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # 创建全局消息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    global_message_id TEXT UNIQUE,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    project_context TEXT DEFAULT '{}',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    token_count INTEGER DEFAULT 0,
                    FOREIGN KEY (conversation_id) REFERENCES global_conversations (id)
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_global_messages_content 
                ON global_messages (content)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_global_messages_project 
                ON global_messages (project_context)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_project 
                ON global_conversations (project_name, project_path)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation 
                ON global_messages (conversation_id)
            """)
            
            conn.commit()
            conn.close()
            
            self.logger.info("全局数据库初始化完成")
        
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
    
    def init_vector_store(self):
        """初始化向量存储"""
        if not self.qdrant_client:
            return
        
        try:
            collection_name = self.vector_config["collection_name"]
            
            # 检查集合是否存在
            collections = self.qdrant_client.get_collections()
            collection_exists = any(
                col.name == collection_name 
                for col in collections.collections
            )
            
            if not collection_exists:
                # 创建集合
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_config.get("vector_size", 384),
                        distance=models.Distance.COSINE
                    )
                )
                self.logger.info(f"创建向量集合: {collection_name}")
            
        except Exception as e:
            self.logger.warning(f"向量存储初始化失败: {e}")
    
    async def health_check(self) -> str:
        """健康检查"""
        try:
            if self.db_path:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM global_conversations")
                conversation_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM global_messages")
                message_count = cursor.fetchone()[0]
                conn.close()
                
                return f"ok - {conversation_count} conversations, {message_count} messages"
            else:
                return "database_not_configured"
        
        except Exception as e:
            return f"error: {str(e)}"
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        try:
            if not self.db_path:
                return {"error": "database_not_configured"}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 基本统计
            cursor.execute("SELECT COUNT(*) FROM global_conversations")
            conversation_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM global_messages")
            message_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT project_name) FROM global_conversations")
            project_count = cursor.fetchone()[0]
            
            # 最近活动
            cursor.execute("""
                SELECT last_activity FROM global_conversations 
                ORDER BY last_activity DESC LIMIT 1
            """)
            last_activity = cursor.fetchone()
            
            conn.close()
            
            return {
                "conversation_count": conversation_count,
                "message_count": message_count,
                "project_count": project_count,
                "last_activity": last_activity[0] if last_activity else None
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    async def search_memories(
        self, 
        query: str, 
        limit: int = 5,
        project_filter: Optional[str] = None,
        current_project: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """搜索全局记忆"""
        try:
            if not self.db_path:
                return {"error": "database_not_configured"}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 构建搜索SQL
            base_sql = """
                SELECT 
                    gm.content,
                    gm.message_type,
                    gm.created_at,
                    gm.project_context,
                    gc.project_name,
                    gc.title
                FROM global_messages gm
                JOIN global_conversations gc ON gm.conversation_id = gc.id
                WHERE gm.content LIKE ?
            """
            
            params = [f"%{query}%"]
            
            # 添加项目过滤
            if project_filter:
                base_sql += " AND gc.project_name = ?"
                params.append(project_filter)
            
            base_sql += " ORDER BY gm.created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(base_sql, params)
            rows = cursor.fetchall()
            
            results = []
            current_project_name = current_project.get("project_name", "unknown") if current_project else "unknown"
            
            for row in rows:
                content, msg_type, created_at, project_context, project_name, title = row
                
                try:
                    project_ctx = json.loads(project_context) if project_context else {}
                except:
                    project_ctx = {}
                
                is_cross_project = project_name != current_project_name
                
                results.append({
                    "content": content[:200] + "..." if len(content) > 200 else content,
                    "message_type": msg_type,
                    "project": project_name,
                    "conversation_title": title,
                    "timestamp": created_at,
                    "is_cross_project": is_cross_project,
                    "relevance_score": 0.85  # 简化的相关性分数
                })
            
            conn.close()
            
            return {
                "query": query,
                "results": results,
                "total": len(results),
                "cross_project_count": sum(1 for r in results if r["is_cross_project"]),
                "search_context": current_project or {},
                "project_filter": project_filter
            }
        
        except Exception as e:
            self.logger.error(f"搜索记忆失败: {e}")
            return {"error": str(e)}
    
    async def get_project_conversations(
        self, 
        project_name: str, 
        limit: int = 10
    ) -> Dict[str, Any]:
        """获取特定项目的对话历史"""
        try:
            if not self.db_path:
                return {"error": "database_not_configured"}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id,
                    title,
                    created_at,
                    last_activity,
                    message_count,
                    project_path
                FROM global_conversations
                WHERE project_name = ?
                ORDER BY last_activity DESC
                LIMIT ?
            """, (project_name, limit))
            
            rows = cursor.fetchall()
            
            conversations = []
            for row in rows:
                conv_id, title, created_at, last_activity, msg_count, project_path = row
                conversations.append({
                    "id": conv_id,
                    "title": title,
                    "created_at": created_at,
                    "last_activity": last_activity,
                    "message_count": msg_count,
                    "project_path": project_path
                })
            
            conn.close()
            
            return {
                "project_name": project_name,
                "conversations": conversations,
                "total": len(conversations)
            }
        
        except Exception as e:
            self.logger.error(f"获取项目对话失败: {e}")
            return {"error": str(e)}
    
    async def get_cross_project_memories(
        self, 
        topic: str, 
        current_project: str, 
        limit: int = 10
    ) -> Dict[str, Any]:
        """获取跨项目相关记忆"""
        try:
            if not self.db_path:
                return {"error": "database_not_configured"}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    gm.content,
                    gm.message_type,
                    gm.created_at,
                    gc.project_name,
                    gc.title,
                    gc.project_path
                FROM global_messages gm
                JOIN global_conversations gc ON gm.conversation_id = gc.id
                WHERE gm.content LIKE ? 
                AND gc.project_name != ?
                ORDER BY gm.created_at DESC
                LIMIT ?
            """, (f"%{topic}%", current_project, limit))
            
            rows = cursor.fetchall()
            
            memories = []
            for row in rows:
                content, msg_type, created_at, project_name, title, project_path = row
                memories.append({
                    "content": content[:200] + "..." if len(content) > 200 else content,
                    "message_type": msg_type,
                    "timestamp": created_at,
                    "source_project": project_name,
                    "conversation_title": title,
                    "project_path": project_path,
                    "relevance_score": 0.8
                })
            
            conn.close()
            
            return {
                "topic": topic,
                "current_project": current_project,
                "cross_project_memories": memories,
                "total": len(memories)
            }
        
        except Exception as e:
            self.logger.error(f"获取跨项目记忆失败: {e}")
            return {"error": str(e)}
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """获取全局统计信息"""
        try:
            if not self.db_path:
                return {"error": "database_not_configured"}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 项目统计
            cursor.execute("""
                SELECT 
                    project_name,
                    COUNT(*) as conversation_count,
                    SUM(message_count) as total_messages,
                    MAX(last_activity) as last_activity
                FROM global_conversations
                GROUP BY project_name
                ORDER BY conversation_count DESC
            """)
            
            project_stats = []
            for row in cursor.fetchall():
                project_name, conv_count, msg_count, last_activity = row
                project_stats.append({
                    "project_name": project_name,
                    "conversation_count": conv_count,
                    "message_count": msg_count or 0,
                    "last_activity": last_activity
                })
            
            # 总体统计
            cursor.execute("SELECT COUNT(*) FROM global_conversations")
            total_conversations = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM global_messages")
            total_messages = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT project_name) FROM global_conversations")
            total_projects = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total_projects": total_projects,
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "project_stats": project_stats,
                "generated_at": datetime.now().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"获取全局统计失败: {e}")
            return {"error": str(e)}
    
    async def store_conversation(
        self, 
        conversation_data: Dict[str, Any],
        project_context: Dict[str, str]
    ) -> str:
        """存储对话数据"""
        try:
            if not self.db_path:
                return "database_not_configured"
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            conversation_id = str(uuid.uuid4())
            global_conversation_id = f"{project_context['project_name']}_{conversation_id}"
            
            # 存储对话
            cursor.execute("""
                INSERT INTO global_conversations (
                    id, project_path, project_name, project_type, global_conversation_id,
                    title, created_at, last_activity, metadata
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
            
            # 存储消息
            for message in conversation_data.get("messages", []):
                message_id = str(uuid.uuid4())
                global_message_id = f"{global_conversation_id}_{message_id}"
                
                # 分析消息内容
                content_analysis = self._analyze_message_content(message.get("content", ""))
                
                cursor.execute("""
                    INSERT INTO global_messages (
                        id, conversation_id, global_message_id, message_type, role,
                        content, content_hash, project_context, message_metadata,
                        created_at, has_code, code_language, file_references
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_id,
                    conversation_id,
                    global_message_id,
                    message.get("type", "user"),
                    message.get("role", "user"),
                    message.get("content", ""),
                    content_analysis["content_hash"],
                    json.dumps(project_context),
                    json.dumps(message.get("metadata", {})),
                    datetime.now().isoformat(),
                    content_analysis["has_code"],
                    content_analysis["code_language"],
                    json.dumps(content_analysis["file_references"])
                ))
            
            # 更新对话消息计数
            cursor.execute("""
                UPDATE global_conversations 
                SET message_count = (
                    SELECT COUNT(*) FROM global_messages 
                    WHERE conversation_id = ?
                )
                WHERE id = ?
            """, (conversation_id, conversation_id))
            
            conn.commit()
            conn.close()
            
            return conversation_id
        
        except Exception as e:
            self.logger.error(f"存储对话失败: {e}")
            return f"error: {str(e)}"
    
    def _analyze_message_content(self, content: str) -> Dict[str, Any]:
        """分析消息内容"""
        import hashlib
        import re
        
        analysis = {
            "content_hash": hashlib.md5(content.encode()).hexdigest(),
            "has_code": False,
            "code_language": None,
            "file_references": []
        }
        
        # 检测代码块
        code_pattern = r'```(\w+)?\n'
        if re.search(code_pattern, content):
            analysis["has_code"] = True
            
            # 尝试检测语言
            lang_match = re.search(r'```(\w+)', content)
            if lang_match:
                analysis["code_language"] = lang_match.group(1)
        
        # 检测文件引用
        file_patterns = [
            r'`([^`]*\.[a-zA-Z]+)`',  # `filename.ext`
            r'(?:file|path):\s*([^\s]+\.[a-zA-Z]+)',  # file: path/file.ext
            r'([A-Za-z0-9_-]+/[A-Za-z0-9_.-]+\.[a-zA-Z]+)'  # path/file.ext
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            analysis["file_references"].extend(matches)
        
        # 去重文件引用
        analysis["file_references"] = list(set(analysis["file_references"]))
        
        return analysis
    
    async def get_recent_conversations(self, limit: int = 5) -> Dict[str, Any]:
        """获取最近的对话"""
        try:
            if not self.db_path:
                return {"error": "database_not_configured"}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id,
                    title,
                    project_name,
                    last_activity,
                    message_count,
                    project_path
                FROM global_conversations
                ORDER BY last_activity DESC
                LIMIT ?
            """, (limit,))
            
            conversations = []
            for row in cursor.fetchall():
                conv_id, title, project_name, last_activity, msg_count, project_path = row
                conversations.append({
                    "id": conv_id,
                    "title": title,
                    "project_name": project_name,
                    "last_activity": last_activity,
                    "message_count": msg_count,
                    "project_path": project_path
                })
            
            conn.close()
            
            return {
                "recent_conversations": conversations,
                "total": len(conversations)
            }
        
        except Exception as e:
            self.logger.error(f"获取最近对话失败: {e}")
            return {"error": str(e)}
    
    async def get_conversation_messages(
        self, 
        conversation_id: str, 
        limit: int = 20
    ) -> Dict[str, Any]:
        """获取对话消息"""
        try:
            if not self.db_path:
                return {"error": "database_not_configured"}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取对话信息
            cursor.execute("""
                SELECT title, project_name, project_path, created_at
                FROM global_conversations
                WHERE id = ?
            """, (conversation_id,))
            
            conv_info = cursor.fetchone()
            if not conv_info:
                conn.close()
                return {"error": "conversation_not_found"}
            
            title, project_name, project_path, created_at = conv_info
            
            # 获取消息
            cursor.execute("""
                SELECT 
                    content,
                    message_type,
                    role,
                    created_at,
                    has_code,
                    code_language,
                    file_references
                FROM global_messages
                WHERE conversation_id = ?
                ORDER BY created_at
                LIMIT ?
            """, (conversation_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                content, msg_type, role, msg_created_at, has_code, code_lang, file_refs = row
                
                try:
                    file_references = json.loads(file_refs) if file_refs else []
                except:
                    file_references = []
                
                messages.append({
                    "content": content,
                    "type": msg_type,
                    "role": role,
                    "timestamp": msg_created_at,
                    "has_code": bool(has_code),
                    "code_language": code_lang,
                    "file_references": file_references
                })
            
            conn.close()
            
            return {
                "conversation": {
                    "id": conversation_id,
                    "title": title,
                    "project_name": project_name,
                    "project_path": project_path,
                    "created_at": created_at
                },
                "messages": messages,
                "total_messages": len(messages)
            }
        
        except Exception as e:
            self.logger.error(f"获取对话消息失败: {e}")
            return {"error": str(e)}