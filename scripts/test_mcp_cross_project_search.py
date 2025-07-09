#!/usr/bin/env python3
"""
使用MCP方式测试跨项目搜索功能
"""

import asyncio
import json
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 设置环境变量
os.environ["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")

# 导入MCP服务器
from claude_memory.mcp_server import main as run_mcp_server

async def test_cross_project_search():
    """测试跨项目搜索"""
    print("=== 测试跨项目搜索功能（通过MCP协议）===\n")
    
    # 通过环境变量设置测试模式
    os.environ["MCP_TEST_MODE"] = "true"
    
    # 运行MCP服务器的主函数（这会初始化所有服务）
    from claude_memory.mcp_server import MCPServer
    mcp = MCPServer()
    
    # 等待服务初始化
    await asyncio.sleep(2)
    
    # 测试用例
    test_queries = [
        {
            "description": "搜索星云智能（所有项目）",
            "query": "星云智能",
            "include_all_projects": True
        },
        {
            "description": "搜索CEO张晓峰",
            "query": "张晓峰 CEO",
            "include_all_projects": True
        },
        {
            "description": "在nebula_test项目中搜索",
            "query": "星云智能 AI产品",
            "project_ids": ["nebula_test"]
        },
        {
            "description": "搜索不存在的内容",
            "query": "这是一个不存在的内容测试",
            "include_all_projects": True
        }
    ]
    
    for test in test_queries:
        print(f"\n--- {test['description']} ---")
        
        # 构建参数
        params = {
            "query": test["query"],
            "limit": 5
        }
        
        if test.get("include_all_projects"):
            params["include_all_projects"] = True
        elif test.get("project_ids"):
            params["project_ids"] = test["project_ids"]
        
        try:
            # 调用跨项目搜索方法
            result_str = await mcp.claude_memory_cross_project_search(**params)
            
            # 解析结果
            result = json.loads(result_str)
            
            print(f"查询: {test['query']}")
            print(f"搜索的项目数: {result.get('projects_searched', 0)}")
            print(f"找到的总结果数: {result.get('total_count', 0)}")
            
            # 显示项目结果
            project_results = result.get('project_results', {})
            if project_results:
                print("\n按项目分组:")
                for proj_id, proj_data in project_results.items():
                    print(f"  - {proj_id}: {proj_data['total_count']} 条结果")
            
            # 显示前3条结果
            results = result.get('results', [])
            if results:
                print(f"\n前{min(3, len(results))}条结果:")
                for i, item in enumerate(results[:3], 1):
                    memory = item['memory_unit']
                    print(f"\n  {i}. {memory['title']}")
                    print(f"     相关性: {item['relevance_score']:.3f}")
                    print(f"     项目: {memory['project_id']}")
                    print(f"     摘要: {memory['summary'][:100]}...")
                    
        except Exception as e:
            print(f"错误: {str(e)}")

async def main():
    """主函数"""
    await test_cross_project_search()

if __name__ == "__main__":
    asyncio.run(main())