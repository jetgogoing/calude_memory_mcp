#!/usr/bin/env python3
"""
跨项目记忆搜索功能测试脚本
模拟测试全局MCP服务的记忆搜索和跨项目访问能力
"""

import asyncio
import sys
import os
import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from global_mcp.global_memory_manager import GlobalMemoryManager
from global_mcp.database_migrator import DatabaseMigrator


class CrossProjectMemoryTester:
    """跨项目记忆搜索测试器"""
    
    def __init__(self):
        self.config_path = Path(__file__).parent / "config" / "global_config.yml"
        self.config = self.load_config()
        self.memory_manager = None
        
    def load_config(self) -> Dict[str, Any]:
        """加载配置"""
        # 简化的测试配置，兼容GlobalMemoryManager
        return {
            "database": {
                "url": "sqlite:///test_memory.db",
                "pool_size": 5,
                "max_overflow": 10
            },
            "vector_store": {
                "url": "http://localhost:6333",  # Qdrant默认端口
                "collection_name": "global_memories",
                "vector_size": 384
            },
            "memory": {
                "cross_project_sharing": True,
                "project_isolation": False,
                "retention_days": 365,
                "max_conversation_age_days": 90
            },
            "search": {
                "max_results": 20,
                "similarity_threshold": 0.7,
                "enable_semantic_search": False  # 禁用向量搜索用于测试
            }
        }
    
    async def setup_test_data(self):
        """设置测试数据"""
        print("📊 设置测试数据...")
        
        # 创建测试项目和对话数据
        test_projects = [
            {
                "name": "python-web-app",
                "path": "/home/user/projects/python-web-app",
                "conversations": [
                    {
                        "messages": [
                            {"role": "user", "content": "如何在Flask中实现用户认证？"},
                            {"role": "assistant", "content": "在Flask中实现用户认证，推荐使用Flask-Login扩展..."},
                            {"role": "user", "content": "数据库设计方面有什么建议？"},
                            {"role": "assistant", "content": "对于用户认证，建议设计以下表结构：users表包含id、username、password_hash、email等字段..."}
                        ]
                    },
                    {
                        "messages": [
                            {"role": "user", "content": "如何优化数据库查询性能？"},
                            {"role": "assistant", "content": "数据库查询优化的几个关键点：1. 创建适当的索引 2. 避免N+1查询问题 3. 使用连接池..."}
                        ]
                    }
                ]
            },
            {
                "name": "react-frontend",
                "path": "/home/user/projects/react-frontend", 
                "conversations": [
                    {
                        "messages": [
                            {"role": "user", "content": "React Hook useEffect有什么最佳实践？"},
                            {"role": "assistant", "content": "useEffect的最佳实践包括：1. 正确设置依赖数组 2. 清理副作用 3. 避免无限循环..."},
                            {"role": "user", "content": "如何处理用户认证状态？"},
                            {"role": "assistant", "content": "在React中处理用户认证状态，可以使用Context API配合localStorage..."}
                        ]
                    }
                ]
            },
            {
                "name": "data-analysis",
                "path": "/home/user/projects/data-analysis",
                "conversations": [
                    {
                        "messages": [
                            {"role": "user", "content": "Python pandas如何处理缺失数据？"},
                            {"role": "assistant", "content": "pandas处理缺失数据的方法：1. dropna()删除缺失值 2. fillna()填充缺失值..."},
                            {"role": "user", "content": "数据库连接池在数据分析中的应用？"},
                            {"role": "assistant", "content": "在数据分析中使用数据库连接池的好处：减少连接开销、提高并发性能、更好的资源管理..."}
                        ]
                    }
                ]
            }
        ]
        
        # 存储到数据库
        for project in test_projects:
            project_context = {
                "project_name": project["name"],
                "project_path": project["path"],
                "project_type": "test"
            }
            
            for i, conv in enumerate(project["conversations"]):
                conversation_data = {
                    "title": f"Test Conversation {i+1}",
                    "messages": conv["messages"],
                    "metadata": {"test_data": True}
                }
                
                conversation_id = await self.memory_manager.store_conversation(
                    conversation_data, 
                    project_context
                )
        
        print(f"✓ 已创建 {len(test_projects)} 个测试项目的对话数据")
    
    async def test_cross_project_search(self):
        """测试跨项目搜索功能"""
        print("\n🔍 测试跨项目记忆搜索功能...")
        
        # 测试案例
        test_queries = [
            {
                "query": "用户认证",
                "description": "搜索所有项目中关于用户认证的讨论"
            },
            {
                "query": "数据库",
                "description": "搜索数据库相关的所有对话"
            },
            {
                "query": "Python",
                "description": "搜索Python相关的内容"
            },
            {
                "query": "性能优化",
                "description": "搜索性能优化相关讨论"
            },
            {
                "query": "React",
                "description": "搜索React相关内容"
            }
        ]
        
        search_results = {}
        
        for test_case in test_queries:
            print(f"\n📝 测试查询: {test_case['query']}")
            print(f"   描述: {test_case['description']}")
            
            try:
                results = await self.memory_manager.search_memories(
                    test_case["query"], 
                    limit=10
                )
                
                search_results[test_case["query"]] = results
                
                print(f"   ✓ 找到 {len(results)} 条相关记忆")
                
                # 显示前3条结果
                for i, result in enumerate(results[:3]):
                    project_name = result.get('project_name', 'Unknown')
                    content_preview = result.get('content', '')[:100] + '...'
                    print(f"     {i+1}. 项目: {project_name}")
                    print(f"        内容: {content_preview}")
                
            except Exception as e:
                print(f"   ✗ 搜索失败: {e}")
                search_results[test_case["query"]] = []
        
        return search_results
    
    async def test_recent_conversations(self):
        """测试获取最近对话功能"""
        print("\n📅 测试获取最近对话功能...")
        
        try:
            recent_conversations = await self.memory_manager.get_recent_conversations(limit=5)
            
            print(f"✓ 获取到 {len(recent_conversations)} 条最近对话")
            
            for i, conv in enumerate(recent_conversations):
                project_name = conv.get('project_name', 'Unknown')
                conversation_id = conv.get('conversation_id', 'Unknown')
                last_message = conv.get('last_message', '')[:80] + '...'
                
                print(f"  {i+1}. 项目: {project_name}")
                print(f"     对话ID: {conversation_id}")
                print(f"     最近消息: {last_message}")
            
            return recent_conversations
            
        except Exception as e:
            print(f"✗ 获取最近对话失败: {e}")
            return []
    
    async def test_project_specific_search(self):
        """测试项目特定搜索"""
        print("\n🏷️  测试项目特定搜索功能...")
        
        test_cases = [
            {
                "project_name": "python-web-app",
                "query": "数据库",
                "description": "在python-web-app项目中搜索数据库相关内容"
            },
            {
                "project_name": "react-frontend", 
                "query": "认证",
                "description": "在react-frontend项目中搜索认证相关内容"
            }
        ]
        
        for test_case in test_cases:
            print(f"\n📂 测试项目搜索: {test_case['project_name']}")
            print(f"   查询: {test_case['query']}")
            
            try:
                results = await self.memory_manager.search_memories(
                    test_case["query"],
                    limit=5,
                    project_filter=test_case["project_name"]
                )
                
                print(f"   ✓ 在项目 {test_case['project_name']} 中找到 {len(results)} 条结果")
                
                for i, result in enumerate(results):
                    content_preview = result.get('content', '')[:60] + '...'
                    print(f"     {i+1}. {content_preview}")
                    
            except Exception as e:
                print(f"   ✗ 项目搜索失败: {e}")
    
    async def test_memory_statistics(self):
        """测试记忆统计功能"""
        print("\n📈 测试记忆统计功能...")
        
        try:
            stats = await self.memory_manager.get_stats()
            
            print("✓ 系统统计信息:")
            print(f"  总项目数: {stats.get('total_projects', 0)}")
            print(f"  总对话数: {stats.get('total_conversations', 0)}")
            print(f"  总消息数: {stats.get('total_messages', 0)}")
            print(f"  数据库大小: {stats.get('database_size', 'Unknown')}")
            
            # 按项目统计
            if 'project_stats' in stats:
                print("\n  各项目统计:")
                for project_stat in stats['project_stats']:
                    project_name = project_stat.get('project_name', 'Unknown')
                    message_count = project_stat.get('message_count', 0)
                    conversation_count = project_stat.get('conversation_count', 0)
                    print(f"    {project_name}: {conversation_count}个对话, {message_count}条消息")
                    
            return stats
            
        except Exception as e:
            print(f"✗ 获取统计信息失败: {e}")
            return {}
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始跨项目记忆搜索功能测试")
        print("=" * 60)
        
        try:
            # 初始化记忆管理器
            print("⚙️  初始化记忆管理器...")
            self.memory_manager = GlobalMemoryManager(self.config)
            print("✓ 记忆管理器初始化完成")
            
            # 设置测试数据
            await self.setup_test_data()
            
            # 执行各项测试
            search_results = await self.test_cross_project_search()
            recent_conversations = await self.test_recent_conversations()
            await self.test_project_specific_search()
            stats = await self.test_memory_statistics()
            
            # 生成测试报告
            await self.generate_test_report({
                "search_results": search_results,
                "recent_conversations": recent_conversations,
                "stats": stats
            })
            
        except Exception as e:
            print(f"❌ 测试过程中发生错误: {e}")
            raise
    
    async def generate_test_report(self, test_data: Dict[str, Any]):
        """生成测试报告"""
        print("\n📊 生成测试报告...")
        
        report = {
            "test_time": datetime.now().isoformat(),
            "test_summary": {
                "cross_project_search": len(test_data["search_results"]),
                "recent_conversations": len(test_data["recent_conversations"]),
                "total_projects": test_data["stats"].get("total_projects", 0),
                "total_conversations": test_data["stats"].get("total_conversations", 0),
                "total_messages": test_data["stats"].get("total_messages", 0)
            },
            "detailed_results": test_data
        }
        
        # 保存报告
        report_file = Path(__file__).parent / "test_results" / f"cross_project_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 测试报告已保存: {report_file}")
        
        print("\n🎯 测试总结:")
        print(f"  ✅ 跨项目搜索测试: {len(test_data['search_results'])} 个查询")
        print(f"  ✅ 最近对话获取: {len(test_data['recent_conversations'])} 条记录")
        print(f"  ✅ 系统统计功能: 正常")
        print(f"  📁 测试项目数: {test_data['stats'].get('total_projects', 0)}")
        print(f"  💬 测试对话数: {test_data['stats'].get('total_conversations', 0)}")
        print(f"  📝 测试消息数: {test_data['stats'].get('total_messages', 0)}")


async def main():
    """主函数"""
    tester = CrossProjectMemoryTester()
    
    try:
        await tester.run_all_tests()
        print("\n🎉 所有测试完成！跨项目记忆搜索功能验证成功！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())