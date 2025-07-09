#!/usr/bin/env python3
"""
Claude Memory 系统集成测试脚本
通过 API 测试完整的工作流程
"""

import asyncio
import requests
import json
from datetime import datetime
from typing import List, Dict
import time

# API 基础URL
API_BASE_URL = "http://localhost:8000"

# 彩色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")

def print_step(step, text):
    print(f"{Colors.BLUE}[步骤 {step}] {text}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.YELLOW}→ {text}{Colors.ENDC}")

# 测试数据
TEST_CONVERSATIONS = [
    {
        "conversation_id": "test_conv_1",
        "user_id": "test_user",
        "project_id": "test_project",
        "messages": [
            {
                "role": "user",
                "content": "我想学习如何使用Python进行数据分析，应该从哪里开始？"
            },
            {
                "role": "assistant",
                "content": "学习Python数据分析是个很好的选择！我建议从以下几个方面开始：\n\n1. **基础库学习**：\n   - NumPy：用于数值计算和多维数组操作\n   - Pandas：用于数据处理和分析\n\n2. **数据可视化**：\n   - Matplotlib：基础绘图库\n   - Seaborn：统计图形的高级接口\n\n3. **统计分析**：\n   - SciPy：科学计算库\n   - StatsModels：统计建模\n\n4. **机器学习入门**：\n   - Scikit-learn：机器学习算法库\n\n推荐从Pandas开始，因为它是数据分析的核心工具。"
            },
            {
                "role": "user",
                "content": "Pandas和NumPy有什么区别？我应该先学哪个？"
            },
            {
                "role": "assistant",
                "content": "很好的问题！让我解释一下它们的区别：\n\n**NumPy**：\n- 主要用于数值计算和多维数组操作\n- 提供高性能的数组对象（ndarray）\n- 适合进行数学运算和科学计算\n- 是许多其他库的基础\n\n**Pandas**：\n- 建立在NumPy基础上\n- 专门用于数据处理和分析\n- 提供DataFrame和Series等高级数据结构\n- 更适合处理表格数据和时间序列\n\n**学习顺序建议**：\n1. 先学习NumPy的基础知识（1-2周）\n2. 然后深入学习Pandas（这会是你主要使用的工具）\n\nNumPy的基础知识会帮助你更好地理解Pandas的底层原理。"
            }
        ]
    },
    {
        "conversation_id": "test_conv_2",
        "user_id": "test_user",
        "project_id": "test_project",
        "messages": [
            {
                "role": "user",
                "content": "请解释一下Claude Memory系统的架构设计"
            },
            {
                "role": "assistant",
                "content": "Claude Memory系统采用了现代化的双层存储架构，设计目标是实现高效的对话记忆管理：\n\n**核心架构组件**：\n\n1. **持久化层 - PostgreSQL**：\n   - 存储完整的对话历史\n   - 保存用户信息和项目数据\n   - 确保数据的持久性和一致性\n\n2. **向量检索层 - Qdrant**：\n   - 存储对话的向量表示\n   - 支持高速语义相似度搜索\n   - 优化检索性能\n\n3. **处理管道**：\n   - ConversationCollector：收集对话\n   - SemanticCompressor：压缩成记忆单元\n   - SemanticRetriever：语义检索\n   - MemoryFuser：记忆融合\n\n这种架构既保证了数据的完整性，又提供了高效的检索能力。"
            }
        ]
    },
    {
        "conversation_id": "test_conv_3",
        "user_id": "test_user",
        "project_id": "test_project",
        "messages": [
            {
                "role": "user",
                "content": "如何优化大规模数据处理的性能？"
            },
            {
                "role": "assistant",
                "content": "优化大规模数据处理性能可以从以下几个方面着手：\n\n1. **数据存储优化**：\n   - 使用列式存储（如Parquet）\n   - 数据分区和索引\n   - 压缩存储\n\n2. **计算优化**：\n   - 并行处理（使用Dask、Spark）\n   - 向量化操作\n   - 减少数据移动\n\n3. **内存管理**：\n   - 分块处理大文件\n   - 使用内存映射\n   - 及时释放不需要的对象\n\n4. **算法优化**：\n   - 选择合适的算法复杂度\n   - 使用近似算法\n   - 缓存中间结果"
            }
        ]
    }
]

def test_health_check():
    """测试健康检查接口"""
    print_step(1, "测试健康检查")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print_success(f"API 服务健康: {response.json()}")
            return True
        else:
            print_error(f"健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"无法连接到API服务: {e}")
        return False

def test_store_conversations():
    """测试存储对话"""
    print_step(2, "测试存储对话到系统")
    stored_ids = []
    
    for conv in TEST_CONVERSATIONS:
        try:
            # 准备请求数据
            payload = {
                "conversation_id": conv["conversation_id"],
                "user_id": conv["user_id"],
                "project_id": conv["project_id"],
                "messages": conv["messages"]
            }
            
            # 发送请求
            response = requests.post(
                f"{API_BASE_URL}/api/v1/conversations",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                stored_ids.append(result.get("conversation_id", conv["conversation_id"]))
                print_success(f"存储对话 {conv['conversation_id']} 成功")
                print_info(f"  - 消息数: {len(conv['messages'])}")
            else:
                print_error(f"存储对话失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            print_error(f"存储对话时发生错误: {e}")
    
    return stored_ids

def test_memory_search(queries: List[str]):
    """测试记忆搜索"""
    print_step(3, "测试语义搜索功能")
    
    for query in queries:
        print_info(f"\n搜索: '{query}'")
        try:
            # 准备搜索请求
            payload = {
                "query": query,
                "project_id": "test_project",
                "limit": 5
            }
            
            # 发送搜索请求
            response = requests.post(
                f"{API_BASE_URL}/api/v1/search",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                results = response.json()
                print_success(f"找到 {len(results.get('results', []))} 个相关记忆")
                
                # 显示搜索结果
                for i, result in enumerate(results.get('results', [])[:3], 1):
                    print_info(f"  [{i}] 相似度: {result.get('score', 0):.3f}")
                    print_info(f"      内容预览: {result.get('content', '')[:100]}...")
            else:
                print_error(f"搜索失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            print_error(f"搜索时发生错误: {e}")

def test_memory_injection():
    """测试记忆注入功能"""
    print_step(4, "测试记忆注入（上下文增强）")
    
    test_prompt = "我想深入学习Python数据分析，特别是Pandas的高级用法"
    
    try:
        # 准备注入请求
        payload = {
            "original_prompt": test_prompt,
            "project_id": "test_project",
            "injection_mode": "balanced",
            "max_tokens": 2000
        }
        
        # 发送注入请求
        response = requests.post(
            f"{API_BASE_URL}/api/v1/inject",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            enhanced_prompt = result.get('enhanced_prompt', '')
            memory_count = result.get('injected_memories', 0)
            
            print_success(f"记忆注入成功")
            print_info(f"  - 注入了 {memory_count} 个相关记忆")
            print_info(f"  - 增强后的提示长度: {len(enhanced_prompt)} 字符")
            print_info(f"\n增强后的提示预览:")
            print(f"{Colors.YELLOW}{enhanced_prompt[:500]}...{Colors.ENDC}")
        else:
            print_error(f"注入失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print_error(f"注入时发生错误: {e}")

def test_project_stats():
    """测试项目统计功能"""
    print_step(5, "测试项目统计")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/projects/test_project/stats"
        )
        
        if response.status_code == 200:
            stats = response.json()
            print_success("获取项目统计成功")
            print_info(f"  - 对话总数: {stats.get('total_conversations', 0)}")
            print_info(f"  - 消息总数: {stats.get('total_messages', 0)}")
            print_info(f"  - 记忆单元数: {stats.get('total_memories', 0)}")
            print_info(f"  - 存储大小: {stats.get('storage_size', 0)} bytes")
        else:
            print_error(f"获取统计失败: {response.status_code}")
            
    except Exception as e:
        print_error(f"获取统计时发生错误: {e}")

def cleanup_test_data():
    """清理测试数据"""
    print_step(6, "清理测试数据")
    
    try:
        # 删除测试对话
        for conv_id in ["test_conv_1", "test_conv_2", "test_conv_3"]:
            response = requests.delete(
                f"{API_BASE_URL}/api/v1/conversations/{conv_id}"
            )
            if response.status_code in [200, 204, 404]:
                print_success(f"清理对话 {conv_id}")
            else:
                print_error(f"清理对话失败: {response.status_code}")
    except Exception as e:
        print_error(f"清理数据时发生错误: {e}")

def main():
    """主测试函数"""
    print_header("Claude Memory 系统集成测试")
    
    # 1. 健康检查
    if not test_health_check():
        print_error("API服务不可用，请确保服务已启动")
        return
    
    # 等待一下确保服务完全就绪
    time.sleep(2)
    
    # 2. 存储对话
    stored_ids = test_store_conversations()
    if not stored_ids:
        print_error("没有成功存储任何对话")
        return
    
    # 等待索引更新
    print_info("\n等待索引更新...")
    time.sleep(3)
    
    # 3. 测试搜索
    test_queries = [
        "Python数据分析学习路径",
        "Pandas和NumPy的区别",
        "Claude Memory系统架构",
        "大规模数据处理优化"
    ]
    test_memory_search(test_queries)
    
    # 4. 测试记忆注入
    test_memory_injection()
    
    # 5. 测试统计
    test_project_stats()
    
    # 6. 清理测试数据
    # cleanup_test_data()  # 暂时注释掉，保留数据用于调试
    
    print_header("测试完成")
    print_success("系统集成测试完成！")
    print_info("\n提示：")
    print_info("- 访问 http://localhost:8000/docs 查看完整API文档")
    print_info("- 查看日志文件了解详细处理过程")
    print_info("- 测试数据已保留，可通过API查询")

if __name__ == "__main__":
    main()