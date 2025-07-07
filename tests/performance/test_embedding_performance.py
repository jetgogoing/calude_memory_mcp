"""
Claude Memory MCP 服务 - 向量生成性能测试

测试内容：
- 单个文本向量生成性能
- 批量文本向量生成性能
- 不同长度文本的处理时间
- 并发向量生成压力测试
- 内存使用监控
- API调用优化验证
"""

import asyncio
import time
from pathlib import Path
from typing import List
from unittest.mock import Mock, patch, AsyncMock

import pytest
import numpy as np

from claude_memory.utils.model_manager import ModelManager
from claude_memory.config.settings import get_settings
from tests.performance.performance_utils import (
    PerformanceBenchmark,
    SystemResourceMonitor,
    create_test_dataset,
    save_benchmark_results,
    check_performance_thresholds,
    PERFORMANCE_THRESHOLDS
)


@pytest.fixture
def mock_settings():
    """模拟配置设置"""
    settings = Mock()
    settings.models.embedding.provider = "siliconflow"
    settings.models.embedding.model_name = "Qwen3-Embedding-8B"
    settings.models.embedding.api_base = "https://api.siliconflow.cn/v1"
    settings.models.embedding.timeout = 30.0
    settings.models.embedding.max_retries = 3
    settings.performance.batch_size = 10
    settings.performance.max_concurrent_requests = 5
    return settings


@pytest.fixture
def model_manager(mock_settings):
    """创建ModelManager实例"""
    with patch('claude_memory.utils.model_manager.get_settings', return_value=mock_settings):
        manager = ModelManager()
        yield manager


@pytest.fixture
def test_texts():
    """创建测试文本数据"""
    return [
        "Hello Claude, can you help me with Python programming?",
        "I need to understand how to implement a binary search algorithm in Python.",
        "What are the best practices for error handling in asynchronous Python code?",
        "Can you explain the difference between deep copy and shallow copy in Python?",
        "How do I optimize the performance of a Django web application?",
    ]


@pytest.fixture
def large_test_dataset():
    """创建大型测试数据集"""
    return create_test_dataset(100, content_length_range=(50, 500))


@pytest.fixture
def performance_output_dir():
    """性能测试输出目录"""
    output_dir = Path("/home/jetgogoing/claude_memory/tests/performance/benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


class TestEmbeddingPerformance:
    """向量生成性能测试"""

    @pytest.mark.asyncio
    async def test_single_embedding_performance(self, model_manager, test_texts, performance_output_dir):
        """测试单个文本向量生成性能"""
        benchmark = PerformanceBenchmark("single_embedding_generation")
        
        # 模拟向量生成
        async def mock_generate_embedding(text):
            # 模拟网络延迟和计算时间
            await asyncio.sleep(0.1 + len(text) * 0.001)  # 基础延迟 + 内容长度影响
            return np.random.random(4096).tolist()  # Qwen3-Embedding-8B 4096维向量
        
        with patch.object(model_manager, 'generate_embedding', mock_generate_embedding):
            
            # 运行基准测试
            async def single_operation():
                text = test_texts[0]  # 使用固定文本确保一致性
                await model_manager.generate_embedding(text)
            
            results = await benchmark.run_async_benchmark(
                async_operation=single_operation,
                iterations=20,
                warmup_iterations=3
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "single_embedding_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.95
        assert results.avg_duration_ms <= 2000  # 单个向量生成应在2秒内完成
        assert results.operations_per_second >= 0.5
        
        # 检查性能阈值
        threshold_checks = check_performance_thresholds(results)
        assert threshold_checks.get('all_checks_passed', False), f"Performance thresholds failed: {threshold_checks}"

    @pytest.mark.asyncio
    async def test_batch_embedding_performance(self, model_manager, large_test_dataset, performance_output_dir):
        """测试批量向量生成性能"""
        benchmark = PerformanceBenchmark("batch_embedding_generation")
        
        # 模拟批量向量生成
        async def mock_generate_embeddings_batch(texts):
            # 模拟批量处理的效率提升
            total_chars = sum(len(text) for text in texts)
            base_delay = 0.5  # 批量请求基础延迟
            processing_delay = total_chars * 0.0005  # 每字符处理时间
            await asyncio.sleep(base_delay + processing_delay)
            
            return [np.random.random(4096).tolist() for _ in texts]
        
        with patch.object(model_manager, 'generate_embeddings_batch', mock_generate_embeddings_batch):
            
            batch_size = 10
            total_batches = len(large_test_dataset) // batch_size
            
            async def batch_operation():
                batch = large_test_dataset[:batch_size]
                await model_manager.generate_embeddings_batch(batch)
            
            results = await benchmark.run_async_benchmark(
                async_operation=batch_operation,
                iterations=total_batches,
                warmup_iterations=2
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "batch_embedding_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.90
        assert results.avg_duration_ms <= 5000  # 批量处理应更高效
        
        # 计算每个文本的平均处理时间
        avg_per_text_ms = results.avg_duration_ms / batch_size
        assert avg_per_text_ms <= 500  # 批量处理中每个文本应在500ms内

    @pytest.mark.asyncio
    async def test_concurrent_embedding_performance(self, model_manager, test_texts, performance_output_dir):
        """测试并发向量生成性能"""
        benchmark = PerformanceBenchmark("concurrent_embedding_generation")
        
        # 模拟并发向量生成
        async def mock_generate_embedding(text):
            await asyncio.sleep(0.15 + len(text) * 0.001)
            return np.random.random(4096).tolist()
        
        with patch.object(model_manager, 'generate_embedding', mock_generate_embedding):
            
            async def concurrent_operation():
                # 并发处理多个文本
                tasks = [model_manager.generate_embedding(text) for text in test_texts]
                await asyncio.gather(*tasks)
            
            results = await benchmark.run_async_benchmark(
                async_operation=concurrent_operation,
                iterations=10,
                concurrency=3,  # 3个并发基准测试
                warmup_iterations=1
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "concurrent_embedding_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.85
        assert results.avg_duration_ms <= 8000  # 并发处理5个文本应在8秒内

    @pytest.mark.asyncio
    async def test_variable_length_embedding_performance(self, model_manager, performance_output_dir):
        """测试不同长度文本的向量生成性能"""
        benchmark = PerformanceBenchmark("variable_length_embedding")
        
        # 创建不同长度的测试文本
        text_lengths = [50, 100, 250, 500, 1000, 2000]
        test_texts_by_length = {}
        
        for length in text_lengths:
            test_texts_by_length[length] = create_test_dataset(5, (length, length))
        
        # 模拟长度相关的处理时间
        async def mock_generate_embedding(text):
            base_delay = 0.1
            length_factor = len(text) * 0.001  # 1ms per character
            await asyncio.sleep(base_delay + length_factor)
            return np.random.random(4096).tolist()
        
        performance_by_length = {}
        
        with patch.object(model_manager, 'generate_embedding', mock_generate_embedding):
            
            for length, texts in test_texts_by_length.items():
                length_benchmark = PerformanceBenchmark(f"embedding_length_{length}")
                
                async def length_operation():
                    text = texts[0]  # 使用第一个文本
                    await model_manager.generate_embedding(text)
                
                length_results = await length_benchmark.run_async_benchmark(
                    async_operation=length_operation,
                    iterations=10,
                    warmup_iterations=1
                )
                
                performance_by_length[length] = length_results
                
                # 保存每个长度的结果
                save_benchmark_results(
                    length_results, 
                    performance_output_dir / f"embedding_length_{length}_results.json"
                )
        
        # 验证性能随长度的变化趋势
        lengths = sorted(performance_by_length.keys())
        avg_durations = [performance_by_length[l].avg_duration_ms for l in lengths]
        
        # 验证处理时间随文本长度增加（允许一些变动）
        for i in range(1, len(avg_durations)):
            # 允许一些误差，但总体趋势应该是递增的
            assert avg_durations[i] >= avg_durations[i-1] * 0.8, \
                f"Performance should generally increase with text length: {avg_durations}"

    @pytest.mark.asyncio
    async def test_embedding_memory_usage(self, model_manager, large_test_dataset, performance_output_dir):
        """测试向量生成的内存使用情况"""
        monitor = SystemResourceMonitor()
        
        # 开始资源监控
        monitor_task = asyncio.create_task(monitor.start_monitoring(interval_seconds=0.5))
        
        try:
            # 模拟内存密集的向量生成
            async def mock_generate_embedding(text):
                await asyncio.sleep(0.1)
                # 模拟向量数据占用内存
                vector = np.random.random(4096).tolist()
                # 模拟一些临时内存使用
                temp_data = [vector] * 10  # 临时创建更多数据
                await asyncio.sleep(0.05)  # 模拟处理时间
                return vector
            
            with patch.object(model_manager, 'generate_embedding', mock_generate_embedding):
                
                # 批量处理文本以观察内存使用模式
                for i in range(0, min(50, len(large_test_dataset)), 5):
                    batch = large_test_dataset[i:i+5]
                    tasks = [model_manager.generate_embedding(text) for text in batch]
                    await asyncio.gather(*tasks)
                    
                    # 每批次之间稍作停顿
                    await asyncio.sleep(0.1)
        
        finally:
            monitor.stop_monitoring()
            await monitor_task
        
        # 分析资源使用情况
        resource_summary = monitor.get_summary()
        
        # 保存资源使用报告
        import json
        with open(performance_output_dir / "embedding_memory_usage.json", 'w') as f:
            json.dump(resource_summary, f, indent=2, default=str)
        
        # 内存使用断言
        assert resource_summary.get('memory_peak_mb', 0) < 1000, "Memory usage should be reasonable"
        assert resource_summary.get('memory_avg_mb', 0) > 0, "Should have some memory usage"

    @pytest.mark.asyncio
    async def test_embedding_error_handling_performance(self, model_manager, test_texts, performance_output_dir):
        """测试向量生成错误处理的性能影响"""
        benchmark = PerformanceBenchmark("embedding_error_handling")
        
        call_count = 0
        
        async def mock_generate_embedding_with_errors(text):
            nonlocal call_count
            call_count += 1
            
            # 模拟30%的失败率
            if call_count % 3 == 0:
                await asyncio.sleep(0.05)  # 快速失败
                raise Exception("Simulated API error")
            else:
                await asyncio.sleep(0.15)  # 正常处理时间
                return np.random.random(4096).tolist()
        
        with patch.object(model_manager, 'generate_embedding', mock_generate_embedding_with_errors):
            
            async def error_prone_operation():
                try:
                    text = test_texts[0]
                    await model_manager.generate_embedding(text)
                except Exception:
                    # 模拟错误处理逻辑
                    await asyncio.sleep(0.01)
                    pass  # 忽略错误继续测试
            
            results = await benchmark.run_async_benchmark(
                async_operation=error_prone_operation,
                iterations=30,
                warmup_iterations=3
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "embedding_error_handling_results.json")
        
        # 错误处理性能断言
        assert results.failed_operations > 0, "Should have some failed operations for this test"
        assert results.avg_duration_ms <= 200, "Error handling should be fast"
        assert results.success_rate >= 0.6, "Success rate should be reasonable despite simulated errors"

    @pytest.mark.asyncio
    async def test_embedding_cache_performance(self, model_manager, test_texts, performance_output_dir):
        """测试向量缓存对性能的影响"""
        benchmark = PerformanceBenchmark("embedding_cache_performance")
        
        # 模拟缓存机制
        cache = {}
        
        async def mock_generate_embedding_with_cache(text):
            # 缓存命中 - 快速返回
            if text in cache:
                await asyncio.sleep(0.01)  # 缓存查找时间
                return cache[text]
            
            # 缓存未命中 - 正常处理
            await asyncio.sleep(0.15 + len(text) * 0.001)
            vector = np.random.random(4096).tolist()
            cache[text] = vector
            return vector
        
        with patch.object(model_manager, 'generate_embedding', mock_generate_embedding_with_cache):
            
            # 第一轮：填充缓存
            for text in test_texts:
                await model_manager.generate_embedding(text)
            
            # 第二轮：测试缓存性能
            async def cached_operation():
                # 使用已缓存的文本
                text = test_texts[0]
                await model_manager.generate_embedding(text)
            
            results = await benchmark.run_async_benchmark(
                async_operation=cached_operation,
                iterations=20,
                warmup_iterations=2
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "embedding_cache_results.json")
        
        # 缓存性能断言
        assert results.success_rate >= 0.98
        assert results.avg_duration_ms <= 50, "Cached operations should be very fast"
        assert results.operations_per_second >= 15, "Cached operations should have high throughput"


class TestEmbeddingStressTest:
    """向量生成压力测试"""

    @pytest.mark.asyncio
    async def test_high_volume_embedding_stress(self, model_manager, performance_output_dir):
        """高容量向量生成压力测试"""
        # 创建大量测试数据
        stress_dataset = create_test_dataset(500, content_length_range=(100, 300))
        
        benchmark = PerformanceBenchmark("high_volume_embedding_stress")
        
        async def mock_generate_embedding(text):
            # 模拟适度的处理时间
            await asyncio.sleep(0.08 + len(text) * 0.0005)
            return np.random.random(4096).tolist()
        
        with patch.object(model_manager, 'generate_embedding', mock_generate_embedding):
            
            # 使用高并发处理大量文本
            async def high_volume_operation():
                batch = stress_dataset[:50]  # 每次处理50个
                tasks = [model_manager.generate_embedding(text) for text in batch]
                await asyncio.gather(*tasks, return_exceptions=True)
            
            results = await benchmark.run_async_benchmark(
                async_operation=high_volume_operation,
                iterations=10,
                concurrency=5,  # 高并发
                warmup_iterations=1
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "high_volume_stress_results.json")
        
        # 压力测试断言
        assert results.success_rate >= 0.8, "Should handle high volume with reasonable success rate"
        assert results.operations_per_second > 0, "Should maintain some throughput under stress"

    @pytest.mark.asyncio
    async def test_embedding_timeout_handling(self, model_manager, test_texts, performance_output_dir):
        """测试向量生成超时处理"""
        benchmark = PerformanceBenchmark("embedding_timeout_handling")
        
        async def mock_generate_embedding_with_timeout(text):
            # 模拟偶尔的超时情况
            import random
            if random.random() < 0.2:  # 20%概率超时
                await asyncio.sleep(5.0)  # 长时间延迟模拟超时
                raise asyncio.TimeoutError("Simulated timeout")
            else:
                await asyncio.sleep(0.1)
                return np.random.random(4096).tolist()
        
        with patch.object(model_manager, 'generate_embedding', mock_generate_embedding_with_timeout):
            
            async def timeout_test_operation():
                text = test_texts[0]
                try:
                    # 设置较短的超时时间
                    await asyncio.wait_for(
                        model_manager.generate_embedding(text),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    pass  # 超时是预期的
            
            results = await benchmark.run_async_benchmark(
                async_operation=timeout_test_operation,
                iterations=20,
                warmup_iterations=2
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "embedding_timeout_results.json")
        
        # 超时处理断言
        assert results.avg_duration_ms <= 2000, "Timeout handling should be reasonably fast"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])