#!/usr/bin/env python3
"""
直接测试跨项目搜索功能 - 使用内部API
"""

import asyncio
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.claude_memory.managers.service_manager import ServiceManager
from src.claude_memory.managers.cross_project_search import CrossProjectSearchRequest
from src.claude_memory.models.data_models import SearchQuery

async def test_cross_project_search():
    """测试跨项目搜索"""
    print("=== 测试跨项目搜索功能 ===\n")
    
    # 初始化服务管理器
    print("初始化服务管理器...")
    service_manager = ServiceManager()
    # ServiceManager 在 __init__ 中自动初始化了组件
    print("✓ 服务管理器初始化完成\n")
    
    # 获取跨项目搜索管理器
    search_manager = service_manager.cross_project_search_manager
    
    # 测试用例
    test_cases = [
        {
            "name": "搜索星云智能（所有项目）",
            "query": "星云智能",
            "include_all": True
        },
        {
            "name": "搜索张晓峰（所有项目）",
            "query": "张晓峰 CEO",
            "include_all": True
        },
        {
            "name": "仅在nebula_test项目中搜索",
            "query": "星云智能",
            "project_ids": ["nebula_test"]
        },
        {
            "name": "搜索AI相关内容（所有项目）",
            "query": "AI 人工智能 产品",
            "include_all": True
        },
        {
            "name": "搜索错误处理（所有项目）",
            "query": "错误处理 异常",
            "include_all": True
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---")
        
        # 构建搜索请求
        search_query = SearchQuery(
            query=test_case["query"],
            query_type="hybrid",
            limit=10,
            min_score=0.3  # 降低阈值以获得更多结果
        )
        
        request = CrossProjectSearchRequest(
            query=search_query,
            include_all_projects=test_case.get("include_all", False),
            project_ids=test_case.get("project_ids"),
            max_results_per_project=5
        )
        
        try:
            # 执行搜索
            result = await search_manager.search_across_projects(request)
            
            print(f"查询: {test_case['query']}")
            print(f"搜索的项目数: {result.projects_searched}")
            print(f"找到的总结果数: {result.total_count}")
            
            # 显示每个项目的结果统计
            if result.project_results:
                print("\n按项目分组的结果:")
                for project_id, project_result in result.project_results.items():
                    print(f"  项目 '{project_id}' ({project_result.project_name}): {project_result.total_count} 条结果")
            
            # 显示前3个结果的详细信息
            if result.results:
                print(f"\n前 {min(3, len(result.results))} 条结果详情:")
                for i, search_result in enumerate(result.results[:3], 1):
                    memory = search_result.memory_unit
                    print(f"\n  {i}. {memory.title}")
                    print(f"     相关性分数: {search_result.relevance_score:.3f}")
                    print(f"     项目ID: {memory.project_id}")
                    print(f"     类型: {memory.unit_type}")
                    print(f"     摘要: {memory.summary[:150]}...")
                    if search_result.matched_keywords:
                        print(f"     匹配关键词: {', '.join(search_result.matched_keywords)}")
            else:
                print("\n没有找到相关结果")
                
        except Exception as e:
            print(f"搜索出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # 显示项目统计信息
    print("\n\n=== 项目统计信息 ===")
    project_manager = service_manager.project_manager
    projects = project_manager.list_projects(only_active=True)
    
    for project in projects:
        stats = project_manager.get_project_statistics(project.id)
        print(f"\n项目: {project.id} ({project.name})")
        print(f"  - 对话数: {stats.get('conversation_count', 0)}")
        print(f"  - 记忆单元数: {stats.get('memory_unit_count', 0)}")
        print(f"  - 总Token数: {stats.get('total_tokens', 0)}")
        print(f"  - 最后活动: {stats.get('last_activity', 'N/A')}")
    
    # 关闭服务
    await service_manager.shutdown()

async def main():
    """主函数"""
    await test_cross_project_search()

if __name__ == "__main__":
    asyncio.run(main())