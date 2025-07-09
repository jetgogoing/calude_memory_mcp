"""
Mini LLM使用示例

展示如何使用Mini LLM处理Reranker输出和生成最终提示词。
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any

from claude_memory.llm import (
    get_mini_llm_manager,
    MiniLLMRequest,
    TaskType
)
from claude_memory.models.data_models import SearchResult


async def process_reranker_output(search_results: List[SearchResult]) -> str:
    """
    处理Reranker输出，生成整理后的摘要
    
    Args:
        search_results: 搜索结果列表
        
    Returns:
        str: 整理后的摘要
    """
    # 获取Mini LLM管理器
    manager = get_mini_llm_manager()
    
    # 构建输入文本
    input_messages = [
        {
            "role": "system", 
            "content": "你是一个记忆整理助手。请将提供的搜索结果整理成一个连贯的摘要，突出重点信息。"
        },
        {
            "role": "user",
            "content": _format_search_results(search_results)
        }
    ]
    
    # 创建请求
    request = MiniLLMRequest(
        task_type=TaskType.COMPLETION,
        input_text=input_messages,
        parameters={
            "max_tokens": 500,
            "temperature": 0.3  # 低温度以保持一致性
        }
    )
    
    # 处理请求
    response = await manager.process(request)
    
    # 记录性能信息
    print(f"[Mini LLM] 模型: {response.model_used}")
    print(f"[Mini LLM] 延迟: {response.latency_ms:.2f}ms")
    print(f"[Mini LLM] 成本: ${response.cost_usd:.6f}")
    
    return response.output


async def generate_final_prompt(
    user_query: str,
    memory_context: str,
    additional_context: Dict[str, Any] = None
) -> str:
    """
    生成包含记忆上下文的最终提示词
    
    Args:
        user_query: 用户查询
        memory_context: 记忆上下文
        additional_context: 额外上下文信息
        
    Returns:
        str: 最终提示词
    """
    # 获取Mini LLM管理器
    manager = get_mini_llm_manager()
    
    # 构建提示
    prompt = f"""基于以下信息生成一个增强的提示词：

用户查询：{user_query}

相关记忆上下文：
{memory_context}

请生成一个包含相关上下文的完整提示词，帮助回答用户的查询。"""

    if additional_context:
        prompt += f"\n\n额外信息：{additional_context}"
    
    # 创建请求
    request = MiniLLMRequest(
        task_type=TaskType.COMPLETION,
        input_text=prompt,
        parameters={
            "max_tokens": 1000,
            "temperature": 0.5
        }
    )
    
    # 处理请求
    response = await manager.process(request)
    
    return response.output


def _format_search_results(results: List[SearchResult]) -> str:
    """格式化搜索结果为文本"""
    formatted = "以下是相关的搜索结果：\n\n"
    
    for idx, result in enumerate(results, 1):
        formatted += f"{idx}. [相关度: {result.score:.2f}] "
        formatted += f"[时间: {result.metadata.get('timestamp', 'N/A')}]\n"
        formatted += f"   内容: {result.content}\n"
        formatted += f"   来源: {result.metadata.get('source', '未知')}\n\n"
    
    return formatted


async def demonstrate_mini_llm():
    """演示Mini LLM功能"""
    print("=== Mini LLM功能演示 ===\n")
    
    # 1. 模拟搜索结果
    search_results = [
        SearchResult(
            id="1",
            content="讨论了使用微服务架构的优势，包括独立部署、技术栈灵活性和团队自治。",
            score=0.95,
            source="conversation",
            metadata={
                "timestamp": "2024-01-15 10:30:00",
                "source": "架构设计会议"
            }
        ),
        SearchResult(
            id="2",
            content="API设计遵循RESTful原则，使用OpenAPI规范进行文档化，确保接口一致性。",
            score=0.87,
            source="conversation",
            metadata={
                "timestamp": "2024-01-14 15:20:00",
                "source": "API设计讨论"
            }
        ),
        SearchResult(
            id="3",
            content="数据库选择PostgreSQL作为主数据库，配置了主从复制以提高可用性。",
            score=0.82,
            source="conversation",
            metadata={
                "timestamp": "2024-01-13 09:45:00",
                "source": "技术选型会议"
            }
        )
    ]
    
    # 2. 处理Reranker输出
    print("1. 处理Reranker输出")
    print("-" * 50)
    summary = await process_reranker_output(search_results)
    print(f"整理后的摘要：\n{summary}\n")
    
    # 3. 生成最终提示词
    print("2. 生成最终提示词")
    print("-" * 50)
    user_query = "我们之前讨论的微服务架构方案是什么？"
    
    final_prompt = await generate_final_prompt(
        user_query=user_query,
        memory_context=summary,
        additional_context={
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "project": "电商平台重构"
        }
    )
    
    print(f"最终提示词：\n{final_prompt}\n")
    
    # 4. 分类任务示例
    print("3. 记忆分类示例")
    print("-" * 50)
    
    manager = get_mini_llm_manager()
    
    classification_request = MiniLLMRequest(
        task_type=TaskType.CLASSIFICATION,
        input_text="讨论了使用Kubernetes进行容器编排，包括服务发现、负载均衡和自动扩缩容。",
        parameters={
            "categories": ["架构设计", "开发实践", "运维部署", "项目管理"]
        }
    )
    
    classification_response = await manager.process(classification_request)
    print(f"分类结果: {classification_response.output}")
    print(f"使用模型: {classification_response.model_used}")
    
    # 5. 关键词提取示例
    print("\n4. 关键词提取示例")
    print("-" * 50)
    
    extraction_request = MiniLLMRequest(
        task_type=TaskType.EXTRACTION,
        input_text="在今天的会议中，我们讨论了使用React和TypeScript构建前端应用，"
                   "后端采用Node.js和Express框架，数据存储使用MongoDB和Redis。",
        parameters={
            "extract_type": "keywords"
        }
    )
    
    extraction_response = await manager.process(extraction_request)
    print(f"提取的关键词: {extraction_response.output}")
    
    # 6. 显示统计信息
    print("\n5. Mini LLM统计信息")
    print("-" * 50)
    
    stats = await manager.get_stats()
    print(f"总请求数: {stats['total_requests']}")
    print(f"缓存命中率: {stats.get('cache_hit_rate', 0):.2%}")
    print(f"平均延迟: {stats.get('average_latency_ms', 0):.2f}ms")
    print(f"平均成本: ${stats.get('average_cost_usd', 0):.6f}")
    print(f"任务分布: {dict(stats.get('task_counts', {}))}")


async def example_with_real_integration():
    """与实际系统集成的示例"""
    print("\n=== 实际系统集成示例 ===\n")
    
    # 模拟从数据库检索到的记忆单元
    memory_units = [
        {
            "content": "项目采用前后端分离架构，前端使用Vue 3 + TypeScript",
            "importance_score": 0.9,
            "created_at": "2024-01-20",
            "tags": ["架构", "前端"]
        },
        {
            "content": "后端API使用FastAPI框架，支持自动生成OpenAPI文档",
            "importance_score": 0.85,
            "created_at": "2024-01-21",
            "tags": ["架构", "后端", "API"]
        },
        {
            "content": "使用Docker Compose进行本地开发环境配置",
            "importance_score": 0.75,
            "created_at": "2024-01-22",
            "tags": ["开发环境", "Docker"]
        }
    ]
    
    # 构建记忆上下文
    memory_context = "\n".join([
        f"- [{unit['created_at']}] {unit['content']} (重要度: {unit['importance_score']})"
        for unit in memory_units
    ])
    
    # 生成增强的提示词
    user_query = "我们的技术栈是什么？"
    
    manager = get_mini_llm_manager()
    
    # 使用DeepSeek Chat生成最终提示词
    request = MiniLLMRequest(
        task_type=TaskType.COMPLETION,
        input_text=[
            {
                "role": "system",
                "content": "你是一个智能助手，基于提供的历史记忆帮助用户回答问题。"
            },
            {
                "role": "user",
                "content": f"""用户问题：{user_query}

历史记忆：
{memory_context}

请基于历史记忆，生成一个详细的回答。"""
            }
        ],
        parameters={
            "max_tokens": 800,
            "temperature": 0.4
        }
    )
    
    response = await manager.process(request)
    
    print(f"用户问题: {user_query}")
    print(f"\n使用模型: {response.model_used} (成本: ${response.cost_usd:.6f})")
    print(f"\n生成的回答:\n{response.output}")


if __name__ == "__main__":
    # 运行演示
    asyncio.run(demonstrate_mini_llm())
    
    # 运行集成示例
    asyncio.run(example_with_real_integration())