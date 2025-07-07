#!/usr/bin/env python3
"""
Claude Memory 数据库迁移器
支持从项目特定数据库迁移到全局数据库Schema
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import uuid


class DatabaseMigrator:
    """数据库迁移器"""
    
    def __init__(self, global_db_path: str, logger: Optional[logging.Logger] = None):
        self.global_db_path = global_db_path
        self.logger = logger or logging.getLogger("database_migrator")
        
        # 确保全局数据库目录存在
        Path(self.global_db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def ensure_global_schema(self) -> bool:
        """确保全局数据库Schema存在"""
        try:
            conn = sqlite3.connect(self.global_db_path)
            cursor = conn.cursor()
            
            # 创建增强的全局对话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_conversations (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    project_type TEXT,  -- git, npm, python, etc.
                    claude_thread_id TEXT,
                    global_conversation_id TEXT UNIQUE,
                    title TEXT,
                    description TEXT,
                    tags TEXT DEFAULT '[]',  -- JSON array of tags
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    token_count INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    migration_source TEXT,  -- 记录迁移来源
                    migration_date TIMESTAMP,
                    is_archived BOOLEAN DEFAULT FALSE,
                    importance_score REAL DEFAULT 0.5
                )
            """)
            
            # 创建增强的全局消息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    global_message_id TEXT UNIQUE,
                    message_type TEXT NOT NULL,  -- user, assistant, system, tool
                    role TEXT,  -- claude, user, system
                    content TEXT NOT NULL,
                    content_hash TEXT,  -- 内容哈希，用于去重
                    project_context TEXT DEFAULT '{}',
                    message_metadata TEXT DEFAULT '{}',
                    parent_message_id TEXT,  -- 用于消息链
                    thread_position INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    token_count INTEGER DEFAULT 0,
                    importance_score REAL DEFAULT 0.5,
                    has_code BOOLEAN DEFAULT FALSE,
                    code_language TEXT,
                    file_references TEXT DEFAULT '[]',  -- JSON array of file paths
                    FOREIGN KEY (conversation_id) REFERENCES global_conversations (id),
                    FOREIGN KEY (parent_message_id) REFERENCES global_messages (id)
                )
            """)
            
            # 创建项目元数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_metadata (
                    id TEXT PRIMARY KEY,
                    project_name TEXT UNIQUE NOT NULL,
                    project_path TEXT NOT NULL,
                    project_type TEXT,  -- git, npm, python, java, etc.
                    git_remote_url TEXT,
                    git_branch TEXT,
                    package_file TEXT,  -- package.json, requirements.txt, etc.
                    last_scan TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    conversation_count INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    first_activity TIMESTAMP,
                    last_activity TIMESTAMP,
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # 创建跨项目引用表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cross_project_references (
                    id TEXT PRIMARY KEY,
                    source_project TEXT NOT NULL,
                    target_project TEXT NOT NULL,
                    reference_type TEXT NOT NULL,  -- mention, code_share, dependency, etc.
                    message_id TEXT,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES global_messages (id)
                )
            """)
            
            # 创建文件引用表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_references (
                    id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    operation_type TEXT,  -- read, write, create, delete, modify
                    line_start INTEGER,
                    line_end INTEGER,
                    context_snippet TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES global_messages (id)
                )
            """)
            
            # 创建优化索引
            self._create_indexes(cursor)
            
            conn.commit()
            conn.close()
            
            self.logger.info("全局数据库Schema创建完成")
            return True
            
        except Exception as e:
            self.logger.error(f"全局Schema创建失败: {e}")
            return False
    
    def _create_indexes(self, cursor):
        """创建数据库索引"""
        indexes = [
            # 对话索引
            "CREATE INDEX IF NOT EXISTS idx_conversations_project ON global_conversations (project_name, project_path)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_activity ON global_conversations (last_activity DESC)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_type ON global_conversations (project_type)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_archived ON global_conversations (is_archived)",
            
            # 消息索引
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON global_messages (conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_content ON global_messages (content)",
            "CREATE INDEX IF NOT EXISTS idx_messages_type ON global_messages (message_type, role)",
            "CREATE INDEX IF NOT EXISTS idx_messages_created ON global_messages (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_messages_hash ON global_messages (content_hash)",
            "CREATE INDEX IF NOT EXISTS idx_messages_code ON global_messages (has_code, code_language)",
            "CREATE INDEX IF NOT EXISTS idx_messages_importance ON global_messages (importance_score DESC)",
            
            # 项目元数据索引
            "CREATE INDEX IF NOT EXISTS idx_project_name ON project_metadata (project_name)",
            "CREATE INDEX IF NOT EXISTS idx_project_type ON project_metadata (project_type)",
            "CREATE INDEX IF NOT EXISTS idx_project_activity ON project_metadata (last_activity DESC)",
            
            # 跨项目引用索引
            "CREATE INDEX IF NOT EXISTS idx_cross_ref_source ON cross_project_references (source_project)",
            "CREATE INDEX IF NOT EXISTS idx_cross_ref_target ON cross_project_references (target_project)",
            "CREATE INDEX IF NOT EXISTS idx_cross_ref_type ON cross_project_references (reference_type)",
            
            # 文件引用索引
            "CREATE INDEX IF NOT EXISTS idx_file_ref_message ON file_references (message_id)",
            "CREATE INDEX IF NOT EXISTS idx_file_ref_project ON file_references (project_name)",
            "CREATE INDEX IF NOT EXISTS idx_file_ref_path ON file_references (file_path)"
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                self.logger.warning(f"索引创建失败: {index_sql} - {e}")
    
    def discover_project_databases(self, search_paths: List[str]) -> List[Dict[str, str]]:
        """发现现有项目数据库"""
        discovered = []
        
        for search_path in search_paths:
            try:
                search_path = Path(search_path).expanduser()
                if not search_path.exists():
                    continue
                
                # 搜索SQLite数据库文件
                for db_pattern in ["*.db", "*.sqlite", "*.sqlite3"]:
                    for db_file in search_path.rglob(db_pattern):
                        if self._is_claude_memory_db(db_file):
                            project_info = self._analyze_project_context(db_file)
                            discovered.append({
                                "db_path": str(db_file),
                                "project_path": project_info["project_path"],
                                "project_name": project_info["project_name"],
                                "project_type": project_info["project_type"],
                                "conversation_count": project_info["conversation_count"],
                                "message_count": project_info["message_count"]
                            })
                            
            except Exception as e:
                self.logger.warning(f"搜索路径扫描失败 {search_path}: {e}")
        
        return discovered
    
    def _is_claude_memory_db(self, db_path: Path) -> bool:
        """检查是否为Claude Memory数据库"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 检查特征表存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('conversations', 'messages')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            
            # 必须同时包含conversations和messages表
            return 'conversations' in tables and 'messages' in tables
            
        except Exception:
            return False
    
    def _analyze_project_context(self, db_path: Path) -> Dict[str, Any]:
        """分析项目上下文"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 获取统计信息
            cursor.execute("SELECT COUNT(*) FROM conversations")
            conversation_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM messages")
            message_count = cursor.fetchone()[0]
            
            conn.close()
            
            # 推断项目信息
            project_path = str(db_path.parent)
            project_name = db_path.parent.name
            project_type = self._detect_project_type(db_path.parent)
            
            return {
                "project_path": project_path,
                "project_name": project_name,
                "project_type": project_type,
                "conversation_count": conversation_count,
                "message_count": message_count
            }
            
        except Exception as e:
            self.logger.warning(f"项目上下文分析失败 {db_path}: {e}")
            return {
                "project_path": str(db_path.parent),
                "project_name": db_path.parent.name,
                "project_type": "unknown",
                "conversation_count": 0,
                "message_count": 0
            }
    
    def _detect_project_type(self, project_path: Path) -> str:
        """检测项目类型"""
        type_indicators = {
            "package.json": "nodejs",
            "requirements.txt": "python",
            "Pipfile": "python",
            "setup.py": "python",
            "pom.xml": "java",
            "build.gradle": "java",
            "Cargo.toml": "rust",
            "go.mod": "go",
            "composer.json": "php",
            ".git": "git"
        }
        
        for indicator, proj_type in type_indicators.items():
            if (project_path / indicator).exists():
                return proj_type
        
        return "unknown"
    
    def migrate_project_database(
        self, 
        source_db_path: str, 
        project_context: Dict[str, str],
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """迁移单个项目数据库"""
        try:
            migration_stats = {
                "source_db": source_db_path,
                "project_name": project_context["project_name"],
                "conversations_migrated": 0,
                "messages_migrated": 0,
                "errors": [],
                "start_time": datetime.now().isoformat(),
                "dry_run": dry_run
            }
            
            if dry_run:
                # 干运行模式，只统计数量
                return self._dry_run_migration(source_db_path, migration_stats)
            
            # 连接源数据库
            source_conn = sqlite3.connect(source_db_path)
            source_cursor = source_conn.cursor()
            
            # 连接全局数据库
            global_conn = sqlite3.connect(self.global_db_path)
            global_cursor = global_conn.cursor()
            
            try:
                # 迁移对话
                self._migrate_conversations(
                    source_cursor, global_cursor, 
                    project_context, migration_stats
                )
                
                # 迁移消息
                self._migrate_messages(
                    source_cursor, global_cursor, 
                    project_context, migration_stats
                )
                
                # 更新项目元数据
                self._update_project_metadata(
                    global_cursor, project_context, migration_stats
                )
                
                global_conn.commit()
                
            except Exception as e:
                global_conn.rollback()
                migration_stats["errors"].append(f"迁移失败: {str(e)}")
                
            finally:
                source_conn.close()
                global_conn.close()
            
            migration_stats["end_time"] = datetime.now().isoformat()
            migration_stats["success"] = len(migration_stats["errors"]) == 0
            
            return migration_stats
            
        except Exception as e:
            self.logger.error(f"项目数据库迁移失败 {source_db_path}: {e}")
            return {
                "source_db": source_db_path,
                "success": False,
                "error": str(e)
            }
    
    def _dry_run_migration(self, source_db_path: str, stats: Dict[str, Any]) -> Dict[str, Any]:
        """干运行迁移统计"""
        try:
            conn = sqlite3.connect(source_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM conversations")
            stats["conversations_to_migrate"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM messages")
            stats["messages_to_migrate"] = cursor.fetchone()[0]
            
            conn.close()
            stats["success"] = True
            
        except Exception as e:
            stats["errors"].append(f"干运行失败: {str(e)}")
            stats["success"] = False
        
        return stats
    
    def _migrate_conversations(
        self, 
        source_cursor, 
        global_cursor, 
        project_context: Dict[str, str], 
        stats: Dict[str, Any]
    ):
        """迁移对话数据"""
        try:
            # 获取源对话数据
            source_cursor.execute("""
                SELECT id, title, created_at, updated_at, message_count, metadata
                FROM conversations
                ORDER BY created_at
            """)
            
            conversations = source_cursor.fetchall()
            
            for conv_data in conversations:
                old_id, title, created_at, updated_at, msg_count, metadata = conv_data
                
                # 生成新的全局ID
                new_id = str(uuid.uuid4())
                global_conversation_id = f"{project_context['project_name']}_{new_id}"
                
                # 插入全局对话
                global_cursor.execute("""
                    INSERT INTO global_conversations (
                        id, project_path, project_name, project_type,
                        global_conversation_id, title, created_at, last_activity,
                        message_count, metadata, migration_source, migration_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_id,
                    project_context["project_path"],
                    project_context["project_name"],
                    project_context.get("project_type", "unknown"),
                    global_conversation_id,
                    title or "Untitled Conversation",
                    created_at,
                    updated_at or created_at,
                    msg_count or 0,
                    metadata or "{}",
                    f"project_migration:{source_cursor}",
                    datetime.now().isoformat()
                ))
                
                # 记录ID映射用于消息迁移
                if not hasattr(self, '_conversation_id_mapping'):
                    self._conversation_id_mapping = {}
                self._conversation_id_mapping[old_id] = new_id
                
                stats["conversations_migrated"] += 1
                
        except Exception as e:
            stats["errors"].append(f"对话迁移失败: {str(e)}")
    
    def _migrate_messages(
        self, 
        source_cursor, 
        global_cursor, 
        project_context: Dict[str, str], 
        stats: Dict[str, Any]
    ):
        """迁移消息数据"""
        try:
            # 获取源消息数据
            source_cursor.execute("""
                SELECT id, conversation_id, role, content, created_at, metadata
                FROM messages
                ORDER BY conversation_id, created_at
            """)
            
            messages = source_cursor.fetchall()
            
            for msg_data in messages:
                old_id, old_conv_id, role, content, created_at, metadata = msg_data
                
                # 获取新的对话ID
                new_conv_id = self._conversation_id_mapping.get(old_conv_id)
                if not new_conv_id:
                    continue  # 跳过没有对应对话的消息
                
                # 生成新的消息ID
                new_id = str(uuid.uuid4())
                global_message_id = f"{project_context['project_name']}_{new_conv_id}_{new_id}"
                
                # 分析消息内容
                content_analysis = self._analyze_message_content(content)
                
                # 插入全局消息
                global_cursor.execute("""
                    INSERT INTO global_messages (
                        id, conversation_id, global_message_id, message_type, role,
                        content, content_hash, project_context, message_metadata,
                        created_at, has_code, code_language, file_references
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_id,
                    new_conv_id,
                    global_message_id,
                    role or "user",
                    role or "user",
                    content,
                    content_analysis["content_hash"],
                    json.dumps(project_context),
                    metadata or "{}",
                    created_at,
                    content_analysis["has_code"],
                    content_analysis["code_language"],
                    json.dumps(content_analysis["file_references"])
                ))
                
                stats["messages_migrated"] += 1
                
        except Exception as e:
            stats["errors"].append(f"消息迁移失败: {str(e)}")
    
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
    
    def _update_project_metadata(
        self, 
        global_cursor, 
        project_context: Dict[str, str], 
        stats: Dict[str, Any]
    ):
        """更新项目元数据"""
        try:
            # 插入或更新项目元数据
            global_cursor.execute("""
                INSERT OR REPLACE INTO project_metadata (
                    id, project_name, project_path, project_type,
                    last_scan, conversation_count, message_count,
                    first_activity, last_activity, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                project_context["project_name"],
                project_context["project_path"],
                project_context.get("project_type", "unknown"),
                datetime.now().isoformat(),
                stats["conversations_migrated"],
                stats["messages_migrated"],
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                json.dumps({"migration_source": "project_database"})
            ))
            
        except Exception as e:
            stats["errors"].append(f"项目元数据更新失败: {str(e)}")
    
    def get_migration_report(self) -> Dict[str, Any]:
        """获取迁移报告"""
        try:
            conn = sqlite3.connect(self.global_db_path)
            cursor = conn.cursor()
            
            # 统计迁移数据
            cursor.execute("SELECT COUNT(*) FROM global_conversations")
            total_conversations = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM global_messages")
            total_messages = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT project_name) FROM global_conversations")
            total_projects = cursor.fetchone()[0]
            
            # 按项目统计
            cursor.execute("""
                SELECT 
                    project_name,
                    COUNT(*) as conversation_count,
                    SUM(message_count) as message_count,
                    project_type,
                    MAX(last_activity) as last_activity
                FROM global_conversations
                GROUP BY project_name
                ORDER BY conversation_count DESC
            """)
            
            project_stats = []
            for row in cursor.fetchall():
                project_name, conv_count, msg_count, proj_type, last_activity = row
                project_stats.append({
                    "project_name": project_name,
                    "conversation_count": conv_count,
                    "message_count": msg_count or 0,
                    "project_type": proj_type,
                    "last_activity": last_activity
                })
            
            conn.close()
            
            return {
                "migration_summary": {
                    "total_projects": total_projects,
                    "total_conversations": total_conversations,
                    "total_messages": total_messages,
                    "report_generated": datetime.now().isoformat()
                },
                "project_breakdown": project_stats
            }
            
        except Exception as e:
            self.logger.error(f"迁移报告生成失败: {e}")
            return {"error": str(e)}