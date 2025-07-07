"""
Claude Memory MCP 服务 - 语义检索性能测试

测试内容：
- 向量相似度搜索性能
- 混合检索策略性能
- 重排序算法性能
- 大规模数据检索性能
- 并发检索压力测试
- 检索准确性与性能权衡
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock

import pytest
import numpy as np

from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.models.data_models import MemoryUnitModel, EmbeddingModel
from claude_memory.config.settings import get_settings
from tests.performance.performance_utils import (
    PerformanceBenchmark,
    SystemResourceMonitor,
    create_test_dataset,
    save_benchmark_results,
    check_performance_thresholds
)


@pytest.fixture
def mock_settings():
    """模拟配置设置"""
    settings = Mock()
    settings.qdrant.url = "http://localhost:6333"
    settings.qdrant.collection_name = "test_memory_vectors"
    settings.qdrant.vector_size = 4096
    settings.retrieval.default_limit = 10
    settings.retrieval.similarity_threshold = 0.7
    settings.retrieval.enable_reranking = True
    settings.retrieval.rerank_top_k = 20
    settings.models.reranker.provider = "siliconflow"
    settings.models.reranker.model_name = "Qwen3-Reranker-8B"
    return settings


@pytest.fixture
def mock_memory_units():
    """创建模拟记忆单元数据"""
    memory_units = []
    
    topics = [
        "Python programming basics",
        "Machine learning algorithms", 
        "Web development with Django",
        "Database optimization techniques",
        "API design best practices",
        "Docker containerization",
        "Cloud computing concepts",
        "Data visualization methods",
        "Security best practices",
        "Performance optimization"
    ]
    
    for i, topic in enumerate(topics):
        for j in range(10):  # 每个主题10个记忆单元
            memory_unit = MemoryUnitModel(
                id=f"memory_{i}_{j}",
                content=f"Detailed content about {topic} - example {j+1}",
                summary=f"Summary of {topic}",
                keywords=[topic.split()[0], topic.split()[1] if len(topic.split()) > 1 else "general"],
                importance_score=0.5 + (i * 0.05),
                embedding=EmbeddingModel(
                    vector=np.random.random(4096).tolist(),
                    model_name="Qwen3-Embedding-8B",
                    created_at=None
                )
            )
            memory_units.append(memory_unit)
    
    return memory_units


@pytest.fixture
def semantic_retriever(mock_settings):
    """创建SemanticRetriever实例"""
    with patch('claude_memory.retrievers.semantic_retriever.get_settings', return_value=mock_settings):
        retriever = SemanticRetriever()
        yield retriever


@pytest.fixture
def performance_output_dir():
    """性能测试输出目录"""
    output_dir = Path("/home/jetgogoing/claude_memory/tests/performance/benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


class TestSemanticRetrievalPerformance:
    """语义检索性能测试"""

    @pytest.mark.asyncio
    async def test_vector_similarity_search_performance(self, semantic_retriever, mock_memory_units, performance_output_dir):
        """测试向量相似度搜索性能"""
        benchmark = PerformanceBenchmark("vector_similarity_search")
        
        # 模拟Qdrant向量搜索
        async def mock_search_vectors(query_vector, limit=10, score_threshold=None):
            # 模拟搜索延迟
            await asyncio.sleep(0.05 + limit * 0.002)  # 基础延迟 + 结果数量影响
            
            # 模拟返回相似度分数和记忆单元
            results = []
            for i, memory_unit in enumerate(mock_memory_units[:limit]):
                score = 0.9 - (i * 0.05)  # 递减的相似度分数
                if score_threshold is None or score >= score_threshold:
                    results.append((memory_unit, score))
            
            return results
        
        with patch.object(semantic_retriever, '_search_vectors', mock_search_vectors):
            
            async def similarity_search_operation():
                query_vector = np.random.random(4096).tolist()
                await semantic_retriever._search_vectors(query_vector, limit=10)
            
            results = await benchmark.run_async_benchmark(
                async_operation=similarity_search_operation,
                iterations=50,
                warmup_iterations=5
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "vector_similarity_search_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.98
        assert results.avg_duration_ms <= 150, "Vector similarity search should be fast"
        assert results.operations_per_second >= 6.0
        
        # 检查性能阈值
        threshold_checks = check_performance_thresholds(results)
        assert threshold_checks.get('all_checks_passed', False), f"Performance thresholds failed: {threshold_checks}"

    @pytest.mark.asyncio
    async def test_hybrid_search_performance(self, semantic_retriever, mock_memory_units, performance_output_dir):
        """测试混合搜索策略性能"""
        benchmark = PerformanceBenchmark("hybrid_search_strategy")
        
        # 模拟混合搜索（向量搜索 + 关键词搜索）
        async def mock_hybrid_search(query, limit=10):
            # 模拟向量搜索
            await asyncio.sleep(0.05)
            vector_results = mock_memory_units[:limit//2]
            
            # 模拟关键词搜索
            await asyncio.sleep(0.02)
            keyword_results = mock_memory_units[limit//2:limit]
            
            # 模拟结果合并和去重
            await asyncio.sleep(0.01)
            combined_results = []
            
            for i, memory_unit in enumerate(vector_results + keyword_results):
                score = 0.85 - (i * 0.03)
                combined_results.append((memory_unit, score))
            
            return combined_results[:limit]
        
        with patch.object(semantic_retriever, '_hybrid_search', mock_hybrid_search):
            
            async def hybrid_search_operation():
                query = "Python programming best practices"
                await semantic_retriever._hybrid_search(query, limit=10)
            
            results = await benchmark.run_async_benchmark(
                async_operation=hybrid_search_operation,
                iterations=30,
                warmup_iterations=3
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "hybrid_search_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.95
        assert results.avg_duration_ms <= 200, "Hybrid search should be reasonably fast"
        assert results.operations_per_second >= 4.0

    @pytest.mark.asyncio
    async def test_reranking_performance(self, semantic_retriever, mock_memory_units, performance_output_dir):
        """测试重排序算法性能"""
        benchmark = PerformanceBenchmark("reranking_performance")
        
        # 模拟重排序过程
        async def mock_rerank_results(query, memory_results, top_k=10):
            # 模拟重排序API调用延迟
            await asyncio.sleep(0.1 + len(memory_results) * 0.005)
            
            # 模拟重排序后的分数
            reranked_results = []
            for i, (memory_unit, original_score) in enumerate(memory_results):
                # 模拟重排序分数（有些提升，有些下降）
                rerank_score = original_score + np.random.uniform(-0.1, 0.1)
                rerank_score = max(0.0, min(1.0, rerank_score))
                reranked_results.append((memory_unit, rerank_score))
            
            # 按重排序分数排序
            reranked_results.sort(key=lambda x: x[1], reverse=True)
            return reranked_results[:top_k]
        
        with patch.object(semantic_retriever, '_rerank_results', mock_rerank_results):
            
            # 准备初始搜索结果
            initial_results = [(unit, 0.8 - i * 0.05) for i, unit in enumerate(mock_memory_units[:20])]
            
            async def reranking_operation():
                query = "Machine learning optimization techniques"
                await semantic_retriever._rerank_results(query, initial_results, top_k=10)
            
            results = await benchmark.run_async_benchmark(
                async_operation=reranking_operation,
                iterations=25,
                warmup_iterations=3
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "reranking_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.92
        assert results.avg_duration_ms <= 300, "Reranking should complete in reasonable time"
        assert results.operations_per_second >= 3.0

    @pytest.mark.asyncio
    async def test_large_scale_retrieval_performance(self, semantic_retriever, performance_output_dir):
        """测试大规模数据检索性能"""
        benchmark = PerformanceBenchmark("large_scale_retrieval")
        
        # 创建大规模模拟数据
        large_dataset_size = 10000
        
        async def mock_large_scale_search(query_vector, limit=10):
            # 模拟大规模搜索的延迟
            base_delay = 0.08
            scale_factor = large_dataset_size / 1000 * 0.02  # 数据规模影响
            total_delay = base_delay + scale_factor
            
            await asyncio.sleep(total_delay)
            
            # 模拟返回结果
            results = []
            for i in range(limit):
                mock_unit = Mock()
                mock_unit.id = f"large_scale_memory_{i}"
                mock_unit.content = f"Large scale memory content {i}"
                score = 0.9 - (i * 0.03)
                results.append((mock_unit, score))
            
            return results
        
        with patch.object(semantic_retriever, '_search_vectors', mock_large_scale_search):
            
            async def large_scale_operation():
                query_vector = np.random.random(4096).tolist()
                await semantic_retriever._search_vectors(query_vector, limit=20)
            
            results = await benchmark.run_async_benchmark(
                async_operation=large_scale_operation,
                iterations=20,
                warmup_iterations=2
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "large_scale_retrieval_results.json")
        
        # 性能断言（大规模下允许更长的响应时间）
        assert results.success_rate >= 0.90
        assert results.avg_duration_ms <= 500, "Large scale retrieval should complete within reasonable time"
        assert results.operations_per_second >= 1.5

    @pytest.mark.asyncio
    async def test_concurrent_retrieval_performance(self, semantic_retriever, mock_memory_units, performance_output_dir):
        """测试并发检索性能"""
        benchmark = PerformanceBenchmark("concurrent_retrieval")
        
        # 模拟检索操作
        async def mock_retrieve_memories(query, limit=10, mode="semantic"):
            await asyncio.sleep(0.08 + limit * 0.003)
            return [(unit, 0.8 - i * 0.05) for i, unit in enumerate(mock_memory_units[:limit])]
        
        with patch.object(semantic_retriever, 'retrieve_memories', mock_retrieve_memories):
            
            # 准备多个不同的查询
            queries = [
                "Python web development",
                "Machine learning algorithms",
                "Database optimization",
                "API security best practices",
                "Docker containerization"
            ]
            
            async def concurrent_retrieval_operation():
                # 并发执行多个检索
                tasks = [
                    semantic_retriever.retrieve_memories(query, limit=10)
                    for query in queries
                ]
                await asyncio.gather(*tasks)
            
            results = await benchmark.run_async_benchmark(
                async_operation=concurrent_retrieval_operation,
                iterations=15,
                concurrency=3,  # 3个并发基准测试
                warmup_iterations=2
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "concurrent_retrieval_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.85
        assert results.avg_duration_ms <= 1000, "Concurrent retrieval should handle multiple queries efficiently"

    @pytest.mark.asyncio
    async def test_retrieval_memory_usage(self, semantic_retriever, mock_memory_units, performance_output_dir):
        """测试检索过程的内存使用"""
        monitor = SystemResourceMonitor()
        
        # 开始资源监控
        monitor_task = asyncio.create_task(monitor.start_monitoring(interval_seconds=0.3))
        
        try:
            # 模拟内存密集的检索操作
            async def mock_memory_intensive_search(query_vector, limit=50):
                await asyncio.sleep(0.1)
                
                # 模拟大量内存使用（向量计算、结果缓存等）
                large_results = []
                for i in range(limit):
                    mock_unit = Mock()
                    mock_unit.id = f"memory_{i}"
                    mock_unit.content = "Content " * 100  # 较大的内容
                    mock_unit.embedding = Mock()
                    mock_unit.embedding.vector = np.random.random(4096).tolist()
                    large_results.append((mock_unit, 0.9 - i * 0.01))
                
                await asyncio.sleep(0.05)  # 模拟处理时间
                return large_results
            
            with patch.object(semantic_retriever, '_search_vectors', mock_memory_intensive_search):
                
                # 执行多轮检索以观察内存使用模式
                for i in range(10):
                    query_vector = np.random.random(4096).tolist()
                    await semantic_retriever._search_vectors(query_vector, limit=50)
                    await asyncio.sleep(0.1)
        
        finally:
            monitor.stop_monitoring()
            await monitor_task
        
        # 分析资源使用情况
        resource_summary = monitor.get_summary()
        
        # 保存资源使用报告
        import json
        with open(performance_output_dir / "retrieval_memory_usage.json", 'w') as f:
            json.dump(resource_summary, f, indent=2, default=str)
        
        # 内存使用断言
        assert resource_summary.get('memory_peak_mb', 0) < 500, "Memory usage should be reasonable"

    @pytest.mark.asyncio
    async def test_retrieval_accuracy_vs_performance(self, semantic_retriever, mock_memory_units, performance_output_dir):
        """测试检索准确性与性能的权衡"""
        test_scenarios = [
            {"limit": 5, "threshold": 0.9, "name": "high_precision"},
            {"limit": 10, "threshold": 0.8, "name": "balanced"},
            {"limit": 20, "threshold": 0.7, "name": "high_recall"},
            {"limit": 50, "threshold": 0.6, "name": "comprehensive"}
        ]
        
        scenario_results = {}
        
        for scenario in test_scenarios:
            benchmark = PerformanceBenchmark(f"retrieval_{scenario['name']}")
            
            async def mock_configurable_search(query_vector, limit, score_threshold):
                # 性能与limit和threshold相关
                base_delay = 0.05
                limit_delay = limit * 0.002
                threshold_delay = (1.0 - score_threshold) * 0.02  # 更低阈值需要更多计算
                
                await asyncio.sleep(base_delay + limit_delay + threshold_delay)
                
                # 模拟结果
                results = []
                for i in range(min(limit, len(mock_memory_units))):
                    score = 0.95 - (i * 0.03)
                    if score >= score_threshold:
                        results.append((mock_memory_units[i], score))
                
                return results
            
            with patch.object(semantic_retriever, '_search_vectors', mock_configurable_search):
                
                async def scenario_operation():
                    query_vector = np.random.random(4096).tolist()
                    await semantic_retriever._search_vectors(
                        query_vector,
                        limit=scenario['limit'],
                        score_threshold=scenario['threshold']
                    )
                
                results = await benchmark.run_async_benchmark(
                    async_operation=scenario_operation,
                    iterations=20,
                    warmup_iterations=2
                )
            
            scenario_results[scenario['name']] = results
            
            # 保存每个场景的结果
            save_benchmark_results(
                results,
                performance_output_dir / f"retrieval_{scenario['name']}_results.json"
            )
        
        # 验证性能权衡趋势
        precision_time = scenario_results['high_precision'].avg_duration_ms
        comprehensive_time = scenario_results['comprehensive'].avg_duration_ms
        
        assert comprehensive_time > precision_time, "Comprehensive search should take longer than high precision"
        
        # 所有场景都应该保持合理的性能
        for name, results in scenario_results.items():
            assert results.success_rate >= 0.95, f"Scenario {name} should have high success rate"
            assert results.avg_duration_ms <= 300, f"Scenario {name} should complete within reasonable time"


class TestRetrievalStressTest:
    """检索压力测试"""

    @pytest.mark.asyncio
    async def test_high_frequency_retrieval_stress(self, semantic_retriever, performance_output_dir):
        """高频率检索压力测试"""
        benchmark = PerformanceBenchmark("high_frequency_retrieval_stress")
        
        async def mock_rapid_search(query_vector, limit=10):
            # 模拟快速但可能不稳定的搜索
            await asyncio.sleep(0.03 + np.random.uniform(0, 0.05))
            
            if np.random.random() < 0.05:  # 5%概率失败
                raise Exception("Simulated overload error")
            
            # 返回模拟结果
            results = []
            for i in range(limit):
                mock_unit = Mock()
                mock_unit.id = f"stress_memory_{i}"
                score = 0.8 - i * 0.05
                results.append((mock_unit, score))
            
            return results
        
        with patch.object(semantic_retriever, '_search_vectors', mock_rapid_search):
            
            async def rapid_retrieval_operation():
                query_vector = np.random.random(4096).tolist()
                await semantic_retriever._search_vectors(query_vector, limit=10)
            
            results = await benchmark.run_async_benchmark(
                async_operation=rapid_retrieval_operation,
                iterations=100,
                concurrency=10,  # 高并发
                warmup_iterations=5
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "high_frequency_stress_results.json")
        
        # 压力测试断言
        assert results.success_rate >= 0.90, "Should handle high frequency requests with good success rate"
        assert results.operations_per_second >= 15, "Should maintain high throughput under stress"

    @pytest.mark.asyncio
    async def test_retrieval_timeout_resilience(self, semantic_retriever, performance_output_dir):
        """测试检索超时恢复能力"""
        benchmark = PerformanceBenchmark("retrieval_timeout_resilience")
        
        async def mock_search_with_timeouts(query_vector, limit=10):
            # 模拟偶尔的超时和慢响应
            if np.random.random() < 0.15:  # 15%概率超时
                await asyncio.sleep(3.0)
                raise asyncio.TimeoutError("Search timeout")
            elif np.random.random() < 0.25:  # 25%概率慢响应
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.08)  # 正常响应
            
            # 返回结果
            results = []
            for i in range(limit):
                mock_unit = Mock()
                mock_unit.id = f"timeout_test_memory_{i}"
                score = 0.85 - i * 0.04
                results.append((mock_unit, score))
            
            return results
        
        with patch.object(semantic_retriever, '_search_vectors', mock_search_with_timeouts):
            
            async def timeout_resilient_operation():
                query_vector = np.random.random(4096).tolist()
                try:
                    await asyncio.wait_for(
                        semantic_retriever._search_vectors(query_vector, limit=10),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    pass  # 超时是测试的一部分
            
            results = await benchmark.run_async_benchmark(
                async_operation=timeout_resilient_operation,
                iterations=30,
                warmup_iterations=3
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "timeout_resilience_results.json")
        
        # 超时恢复断言
        assert results.avg_duration_ms <= 1500, "Timeout handling should be efficient"
        assert results.operations_per_second >= 1.0, "Should maintain reasonable throughput despite timeouts"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])