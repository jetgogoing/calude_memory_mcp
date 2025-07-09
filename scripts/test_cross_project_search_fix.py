#!/usr/bin/env python3
"""
测试跨项目搜索功能 - 验证修复后的功能
"""

import asyncio
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.claude_memory.mcp_server import server
from src.claude_memory.models.data_models import SearchQuery
from mcp.server import Request
import json

async def test_cross_project_search():
    """测试跨项目搜索"""
    print("=== 测试跨项目搜索功能 ===\n")
    
    # 初始化 MCP 服务器
    print("初始化 MCP 服务器...")
    await server._initialize_services()
    print("✓ MCP 服务器初始化完成\n")
    
    # 测试用例
    test_cases = [
        {
            "name": "搜索星云智能",
            "query": "星云智能",
            "include_all": True
        },
        {
            "name": "搜索张晓峰",
            "query": "张晓峰 CEO",
            "include_all": True
        },
        {
            "name": "搜索AI产品",
            "query": "AI产品 智能助手",
            "include_all": True
        },
        {
            "name": "指定nebula_test项目搜索",
            "query": "星云智能",
            "project_ids": ["nebula_test"]
        },
        {
            "name": "搜索所有项目的AI相关内容",
            "query": "AI 人工智能",
            "include_all": True
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---")
        
        # 构建请求参数
        params = {
            "query": test_case["query"],
            "limit": 5
        }
        
        if test_case.get("include_all"):
            params["include_all_projects"] = True
        elif test_case.get("project_ids"):
            params["project_ids"] = test_case["project_ids"]
        
        # 创建 MCP 请求
        request = Request(
            method="claude_memory_cross_project_search",
            params=params
        )
        
        # 调用工具
        try:
            result = await server.claude_memory_cross_project_search(**params)
            
            # 解析结果
            if isinstance(result, str):
                result_data = json.loads(result)
            else:
                result_data = result
            
            print(f"查询: {test_case['query']}")
            print(f"搜索的项目数: {result_data.get('projects_searched', 0)}")
            print(f"找到的结果数: {result_data.get('total_count', 0)}")
            
            # 显示每个项目的结果
            project_results = result_data.get('project_results', {})
            if project_results:
                print("\n按项目分组的结果:")
                for project_id, project_data in project_results.items():
                    print(f"  项目 {project_id}: {project_data.get('total_count', 0)} 条结果")
            
            # 显示前3个结果
            results = result_data.get('results', [])
            if results:
                print(f"\n前 {min(3, len(results))} 条结果:")
                for i, item in enumerate(results[:3], 1):
                    memory = item.get('memory_unit', {})
                    print(f"\n  {i}. {memory.get('title', '无标题')}")
                    print(f"     相关性: {item.get('relevance_score', 0):.3f}")
                    print(f"     项目: {memory.get('project_id', 'unknown')}")
                    print(f"     摘要: {memory.get('summary', '')[:100]}...")
            else:
                print("\n没有找到相关结果")
                
        except Exception as e:
            print(f"错误: {str(e)}")
    
    # 测试特定项目的统计
    print("\n\n=== 项目统计信息 ===")
    if hasattr(server.service_manager, 'project_manager'):
        project_manager = server.service_manager.project_manager
        for project_id in ["default", "nebula_test", "shenrui_investment"]:
            stats = project_manager.get_project_statistics(project_id)
            print(f"\n项目: {project_id}")
            print(f"  - 对话数: {stats.get('conversation_count', 0)}")
            print(f"  - 记忆单元数: {stats.get('memory_unit_count', 0)}")
            print(f"  - 总Token数: {stats.get('total_tokens', 0)}")

async def main():
    """主函数"""
    await test_cross_project_search()

if __name__ == "__main__":
    asyncio.run(main())