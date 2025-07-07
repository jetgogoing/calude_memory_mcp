#!/usr/bin/env python3
"""
跨项目记忆搜索功能演示
演示Claude Memory MCP服务的核心跨项目搜索能力
"""

import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import uuid


class CrossProjectSearchDemo:
    """跨项目记忆搜索演示"""
    
    def __init__(self):
        self.db_path = "demo_memory.db"
        self.init_database()
        self.setup_demo_data()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建简化的表结构
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                title TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """)
        
        conn.commit()
        conn.close()
        print("✓ 数据库初始化完成")
    
    def setup_demo_data(self):
        """设置演示数据"""
        print("📊 设置演示数据...")
        
        demo_projects = [
            {
                "name": "python-web-app",
                "path": "/home/user/projects/python-web-app",
                "conversations": [
                    {
                        "title": "Flask用户认证实现",
                        "messages": [
                            {"role": "user", "content": "如何在Flask中实现用户认证系统？我需要包含登录、注册和权限管理功能。"},
                            {"role": "assistant", "content": "在Flask中实现用户认证系统，推荐使用Flask-Login扩展。首先安装依赖：pip install flask-login flask-wtf。然后创建User模型类，实现UserMixin接口。配置登录管理器，创建登录表单，实现登录视图函数。对于权限管理，可以使用装饰器来保护路由。"},
                            {"role": "user", "content": "数据库设计方面有什么建议？用户表应该包含哪些字段？"},
                            {"role": "assistant", "content": "用户表的核心字段建议包含：id（主键）、username（用户名，唯一）、email（邮箱，唯一）、password_hash（密码哈希，永远不存储明文密码）、created_at（创建时间）、updated_at（更新时间）、is_active（是否激活）、role（用户角色）。可以考虑添加profile相关字段如first_name、last_name、avatar_url等。"}
                        ]
                    },
                    {
                        "title": "数据库性能优化",
                        "messages": [
                            {"role": "user", "content": "我的Flask应用数据库查询越来越慢，有什么优化建议？"},
                            {"role": "assistant", "content": "数据库查询优化的几个关键点：1. 创建适当的索引，特别是WHERE子句和JOIN条件中经常使用的字段；2. 避免N+1查询问题，使用SQLAlchemy的join和eager loading；3. 使用数据库连接池；4. 对大表进行分页查询；5. 考虑使用Redis等缓存系统缓存频繁查询的数据；6. 定期分析慢查询日志，识别性能瓶颈。"}
                        ]
                    }
                ]
            },
            {
                "name": "react-frontend",
                "path": "/home/user/projects/react-frontend",
                "conversations": [
                    {
                        "title": "React Hooks最佳实践",
                        "messages": [
                            {"role": "user", "content": "React Hook useEffect有什么最佳实践？我经常遇到无限循环的问题。"},
                            {"role": "assistant", "content": "useEffect的最佳实践包括：1. 正确设置依赖数组，只包含effect中使用的变量；2. 使用useCallback和useMemo优化依赖；3. 清理副作用，如定时器、事件监听器；4. 避免在effect中直接修改依赖的状态；5. 考虑将复杂的effect拆分为多个小的effect；6. 使用ESLint插件检查依赖数组的正确性。"},
                            {"role": "user", "content": "在React中如何优雅地处理用户认证状态？"},
                            {"role": "assistant", "content": "在React中处理用户认证状态的推荐方案：1. 使用Context API创建AuthContext提供全局认证状态；2. 创建自定义Hook如useAuth来访问认证状态；3. 使用localStorage或sessionStorage持久化token；4. 实现路由守卫组件ProtectedRoute；5. 在axios拦截器中自动添加token和处理401错误；6. 考虑使用状态管理库如Redux进行复杂的状态管理。"}
                        ]
                    }
                ]
            },
            {
                "name": "data-analysis",
                "path": "/home/user/projects/data-analysis",
                "conversations": [
                    {
                        "title": "Pandas数据处理",
                        "messages": [
                            {"role": "user", "content": "Python pandas如何高效处理大量缺失数据？我有一个100万行的数据集。"},
                            {"role": "assistant", "content": "处理大量缺失数据的策略：1. 使用df.info()和df.isnull().sum()先分析缺失模式；2. 对于数值列，可以用均值、中位数或前向填充fillna(method='ffill')；3. 对于分类数据，用众数或创建'Unknown'类别；4. 考虑删除缺失率超过50%的列；5. 使用插值方法interpolate()处理时间序列；6. 对于大数据集，使用chunking技术分块处理：for chunk in pd.read_csv('file.csv', chunksize=10000)。"},
                            {"role": "user", "content": "数据分析项目中如何设计数据库连接池？"},
                            {"role": "assistant", "content": "数据分析项目的数据库连接池设计要点：1. 使用SQLAlchemy的连接池，配置pool_size和max_overflow；2. 对于读密集型分析，考虑读写分离；3. 设置合理的连接超时时间；4. 使用连接池监控，tracking连接使用情况；5. 对于长时间运行的分析任务，定期回收连接防止连接泄漏；6. 考虑使用异步数据库驱动如asyncpg提高并发性能。"}
                        ]
                    }
                ]
            }
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for project_data in demo_projects:
            # 插入项目
            project_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO projects (id, name, path, created_at)
                VALUES (?, ?, ?, ?)
            """, (project_id, project_data["name"], project_data["path"], datetime.now().isoformat()))
            
            for conv_data in project_data["conversations"]:
                # 插入对话
                conversation_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO conversations (id, project_id, title, created_at)
                    VALUES (?, ?, ?, ?)
                """, (conversation_id, project_id, conv_data["title"], datetime.now().isoformat()))
                
                for msg in conv_data["messages"]:
                    # 插入消息
                    message_id = str(uuid.uuid4())
                    content_hash = hashlib.md5(msg["content"].encode()).hexdigest()
                    cursor.execute("""
                        INSERT INTO messages (id, conversation_id, role, content, content_hash, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (message_id, conversation_id, msg["role"], msg["content"], content_hash, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"✓ 已创建 {len(demo_projects)} 个项目的演示数据")
    
    def cross_project_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """跨项目搜索功能"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 使用SQL全文搜索（简单的LIKE查询）
        cursor.execute("""
            SELECT 
                m.content,
                m.role,
                c.title as conversation_title,
                p.name as project_name,
                p.path as project_path,
                m.created_at
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            JOIN projects p ON c.project_id = p.id
            WHERE m.content LIKE ?
            ORDER BY m.created_at DESC
            LIMIT ?
        """, (f"%{query}%", limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "content": row[0],
                "role": row[1],
                "conversation_title": row[2],
                "project_name": row[3],
                "project_path": row[4],
                "created_at": row[5]
            })
        
        conn.close()
        return results
    
    def get_recent_conversations(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取最近对话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.id,
                c.title,
                p.name as project_name,
                p.path as project_path,
                c.created_at,
                (SELECT content FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message
            FROM conversations c
            JOIN projects p ON c.project_id = p.id
            ORDER BY c.created_at DESC
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "conversation_id": row[0],
                "title": row[1],
                "project_name": row[2],
                "project_path": row[3],
                "created_at": row[4],
                "last_message": row[5]
            })
        
        conn.close()
        return results
    
    def get_project_specific_search(self, project_name: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """项目特定搜索"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.content,
                m.role,
                c.title as conversation_title,
                m.created_at
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            JOIN projects p ON c.project_id = p.id
            WHERE p.name = ? AND m.content LIKE ?
            ORDER BY m.created_at DESC
            LIMIT ?
        """, (project_name, f"%{query}%", limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "content": row[0],
                "role": row[1],
                "conversation_title": row[2],
                "created_at": row[3]
            })
        
        conn.close()
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总体统计
        cursor.execute("SELECT COUNT(*) FROM projects")
        total_projects = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_conversations = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        
        # 按项目统计
        cursor.execute("""
            SELECT 
                p.name,
                COUNT(DISTINCT c.id) as conversation_count,
                COUNT(m.id) as message_count
            FROM projects p
            LEFT JOIN conversations c ON p.id = c.project_id
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY p.id, p.name
        """)
        
        project_stats = []
        for row in cursor.fetchall():
            project_stats.append({
                "project_name": row[0],
                "conversation_count": row[1],
                "message_count": row[2]
            })
        
        conn.close()
        
        return {
            "total_projects": total_projects,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "project_stats": project_stats
        }
    
    def demonstrate_all_features(self):
        """演示所有功能"""
        print("\n" + "="*80)
        print("🧠 Claude Memory MCP 跨项目记忆搜索功能演示")
        print("="*80)
        
        # 1. 跨项目搜索
        print("\n🔍 1. 跨项目记忆搜索测试")
        print("-"*50)
        
        test_queries = [
            "用户认证",
            "数据库", 
            "React",
            "Python",
            "性能优化"
        ]
        
        for query in test_queries:
            print(f"\n📝 搜索: '{query}'")
            results = self.cross_project_search(query, limit=3)
            print(f"   找到 {len(results)} 条相关记忆")
            
            for i, result in enumerate(results):
                project_name = result['project_name']
                content_preview = result['content'][:100] + "..."
                conversation_title = result['conversation_title']
                print(f"     {i+1}. 项目: {project_name}")
                print(f"        对话: {conversation_title}")
                print(f"        内容: {content_preview}")
        
        # 2. 最近对话
        print(f"\n📅 2. 最近对话获取")
        print("-"*50)
        
        recent_conversations = self.get_recent_conversations(limit=5)
        print(f"获取到 {len(recent_conversations)} 条最近对话:")
        
        for i, conv in enumerate(recent_conversations):
            project_name = conv['project_name']
            title = conv['title']
            last_message = conv['last_message'][:80] + "..."
            print(f"  {i+1}. 项目: {project_name}")
            print(f"     标题: {title}")
            print(f"     最近消息: {last_message}")
        
        # 3. 项目特定搜索
        print(f"\n🏷️  3. 项目特定搜索")
        print("-"*50)
        
        project_searches = [
            ("python-web-app", "数据库"),
            ("react-frontend", "认证"),
            ("data-analysis", "pandas")
        ]
        
        for project_name, query in project_searches:
            print(f"\n📂 在项目 '{project_name}' 中搜索 '{query}':")
            results = self.get_project_specific_search(project_name, query, limit=2)
            print(f"   找到 {len(results)} 条结果")
            
            for i, result in enumerate(results):
                content_preview = result['content'][:80] + "..."
                conversation_title = result['conversation_title']
                print(f"     {i+1}. 对话: {conversation_title}")
                print(f"        内容: {content_preview}")
        
        # 4. 统计信息
        print(f"\n📈 4. 系统统计信息")
        print("-"*50)
        
        stats = self.get_statistics()
        print(f"系统概览:")
        print(f"  总项目数: {stats['total_projects']}")
        print(f"  总对话数: {stats['total_conversations']}")
        print(f"  总消息数: {stats['total_messages']}")
        
        print(f"\n各项目详情:")
        for project_stat in stats['project_stats']:
            name = project_stat['project_name']
            convs = project_stat['conversation_count']
            msgs = project_stat['message_count']
            print(f"  {name}: {convs}个对话, {msgs}条消息")
        
        print(f"\n🎯 演示总结:")
        print("✅ 跨项目记忆搜索: 可以在所有项目中搜索相关内容")
        print("✅ 项目特定搜索: 可以限定在特定项目中搜索")
        print("✅ 最近对话获取: 可以获取最新的对话记录")
        print("✅ 统计信息查看: 可以查看系统和项目的详细统计")
        print("✅ 跨项目记忆共享: 项目A的经验可以在项目B中被搜索到")
        
        print(f"\n💡 使用场景示例:")
        print("- 在新项目中快速找到之前讨论过的技术方案")
        print("- 跨项目复用代码片段和最佳实践")
        print("- 查找特定技术栈的问题解决方案")
        print("- 追踪技术决策的演进历程")
        
        print(f"\n🔧 MCP集成:")
        print("- 通过Claude CLI调用: claude mcp call claude-memory-global memory_search")
        print("- 支持所有主要操作: 搜索、获取最近对话、项目筛选、统计查看")
        print("- 完全透明的跨项目访问，无需手动切换上下文")


def main():
    """主函数"""
    demo = CrossProjectSearchDemo()
    demo.demonstrate_all_features()
    
    print(f"\n🎉 Claude Memory MCP 跨项目记忆搜索功能演示完成！")
    print(f"数据库文件: {demo.db_path}")


if __name__ == "__main__":
    main()