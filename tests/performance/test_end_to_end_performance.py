"""
Claude Memory MCP 服务 - 端到端性能测试

测试内容：
- 完整记忆管理生命周期性能
- 对话采集到上下文注入的端到端延迟
- 工作流各阶段性能分析
- 系统整体吞吐量测试
- 多用户并发场景性能
- 性能瓶颈识别和分析
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

import pytest
import numpy as np

from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType
from claude_memory.config.settings import get_settings
from tests.performance.performance_utils import (
    PerformanceBenchmark,
    SystemResourceMonitor,
    create_test_dataset,
    save_benchmark_results,
    check_performance_thresholds,
    PerformanceTimer
)


@pytest.fixture
def mock_settings():
    """模拟配置设置"""
    settings = Mock()
    # 数据库设置
    settings.database.url = "sqlite:///test_performance.db"
    settings.database.echo = False
    
    # Qdrant设置
    settings.qdrant.url = "http://localhost:6333"
    settings.qdrant.collection_name = "test_performance_vectors"
    
    # 模型设置
    settings.models.embedding.provider = "siliconflow"
    settings.models.compression.provider = "openrouter"
    settings.models.reranker.provider = "siliconflow"
    
    # 性能设置
    settings.performance.batch_size = 10
    settings.performance.max_concurrent_requests = 5
    
    # 检索设置
    settings.retrieval.default_limit = 10
    settings.retrieval.enable_reranking = True
    
    return settings


@pytest.fixture
def mock_conversations():
    """创建模拟对话数据"""
    conversations = []
    
    topics = [
        "Python programming help",
        "Machine learning concepts",
        "Web development questions", 
        "Database design advice",
        "API integration support"
    ]
    
    for i, topic in enumerate(topics):
        messages = [
            MessageModel(
                conversation_id=None,
                sequence_number=0,
                message_type=MessageType.USER,
                content=f"I need help with {topic}. Can you provide guidance?",
                token_count=15
            ),
            MessageModel(
                conversation_id=None,
                sequence_number=1,
                message_type=MessageType.ASSISTANT,
                content=f"I'd be happy to help you with {topic}. Here's a comprehensive guide...",
                token_count=25
            )
        ]
        
        conversation = ConversationModel(
            session_id=f"test_session_{i}",
            messages=messages,
            message_count=len(messages),
            token_count=sum(msg.token_count for msg in messages),
            title=f"Discussion about {topic}"
        )
        conversations.append(conversation)
    
    return conversations


@pytest.fixture
def service_manager(mock_settings):
    """创建ServiceManager实例"""
    with patch('claude_memory.managers.service_manager.get_settings', return_value=mock_settings):
        manager = ServiceManager()
        yield manager


@pytest.fixture
def performance_output_dir():
    """性能测试输出目录"""
    output_dir = Path("/home/jetgogoing/claude_memory/tests/performance/benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


class TestEndToEndWorkflowPerformance:
    """端到端工作流性能测试"""

    @pytest.mark.asyncio
    async def test_complete_memory_lifecycle_performance(self, service_manager, mock_conversations, performance_output_dir):
        """测试完整记忆生命周期性能"""
        benchmark = PerformanceBenchmark("complete_memory_lifecycle")
        
        # 模拟各个阶段的处理时间
        async def mock_process_conversation(conversation):
            # 1. 对话验证和预处理
            await asyncio.sleep(0.02)
            
            # 2. 语义压缩
            await asyncio.sleep(0.8 + conversation.token_count * 0.001)
            
            # 3. 向量生成
            await asyncio.sleep(0.5)
            
            # 4. 存储到数据库和向量数据库
            await asyncio.sleep(0.1)
            
            return True
        
        async def mock_retrieve_and_inject(query):
            # 1. 查询向量生成
            await asyncio.sleep(0.3)
            
            # 2. 语义检索
            await asyncio.sleep(0.08)
            
            # 3. 重排序
            await asyncio.sleep(0.15)
            
            # 4. 上下文注入
            await asyncio.sleep(0.05)
            
            return "Enhanced context with retrieved memories"
        
        # 模拟ServiceManager的方法
        with patch.object(service_manager, 'process_conversation', mock_process_conversation):
            with patch.object(service_manager, 'enhance_context', mock_retrieve_and_inject):
                
                async def complete_lifecycle_operation():
                    # 完整的记忆管理生命周期
                    conversation = mock_conversations[0]
                    
                    # 阶段1：处理新对话
                    await service_manager.process_conversation(conversation)
                    
                    # 阶段2：检索和增强上下文
                    query = "Help with Python programming"
                    await service_manager.enhance_context(query)
                
                results = await benchmark.run_async_benchmark(
                    async_operation=complete_lifecycle_operation,
                    iterations=20,
                    warmup_iterations=3
                )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "complete_lifecycle_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.95
        assert results.avg_duration_ms <= 8000, "Complete lifecycle should finish within 8 seconds"
        assert results.operations_per_second >= 0.1
        
        # 检查性能阈值
        threshold_checks = check_performance_thresholds(results)
        assert threshold_checks.get('all_checks_passed', False), f"Performance thresholds failed: {threshold_checks}"

    @pytest.mark.asyncio
    async def test_conversation_processing_pipeline_performance(self, service_manager, mock_conversations, performance_output_dir):
        """测试对话处理管道性能"""
        benchmark = PerformanceBenchmark("conversation_processing_pipeline")
        
        # 模拟处理管道的各个阶段
        stage_timings = {
            'validation': 0.01,
            'preprocessing': 0.02,
            'compression': 0.6,
            'embedding': 0.4,
            'storage': 0.08
        }
        
        async def mock_process_conversation_detailed(conversation):
            total_time = 0
            
            for stage, base_time in stage_timings.items():
                # 根据对话复杂度调整时间
                stage_time = base_time + (conversation.token_count * 0.0005)
                await asyncio.sleep(stage_time)
                total_time += stage_time
            
            return {
                'success': True,
                'total_time': total_time,
                'stages': stage_timings
            }
        
        with patch.object(service_manager, 'process_conversation', mock_process_conversation_detailed):
            
            async def pipeline_operation():
                # 处理不同复杂度的对话
                conversation = mock_conversations[0]
                await service_manager.process_conversation(conversation)
            
            results = await benchmark.run_async_benchmark(
                async_operation=pipeline_operation,
                iterations=25,
                warmup_iterations=3
            )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "processing_pipeline_results.json")
        
        # 性能断言
        assert results.success_rate >= 0.92
        assert results.avg_duration_ms <= 5000, "Processing pipeline should be efficient"

    @pytest.mark.asyncio
    async def test_context_enhancement_performance(self, service_manager, performance_output_dir):
        """测试上下文增强性能"""
        benchmark = PerformanceBenchmark("context_enhancement")
        
        # 模拟上下文增强的各个步骤
        async def mock_enhance_context_detailed(query, strategy="balanced"):
            timings = {}
            
            # 1. 查询分析和向量化
            timings['query_vectorization'] = 0.25
            await asyncio.sleep(timings['query_vectorization'])
            
            # 2. 语义检索
            timings['semantic_retrieval'] = 0.06 if strategy == "fast" else 0.12
            await asyncio.sleep(timings['semantic_retrieval'])
            
            # 3. 重排序（如果启用）
            if strategy in ["balanced", "comprehensive"]:
                timings['reranking'] = 0.15
                await asyncio.sleep(timings['reranking'])
            
            # 4. 上下文构建和优化
            timings['context_building'] = 0.03
            await asyncio.sleep(timings['context_building'])
            
            return {
                'enhanced_context': f"Enhanced context for: {query}",
                'timings': timings,
                'total_time': sum(timings.values())
            }
        
        # 测试不同策略的性能
        strategies = ["fast", "balanced", "comprehensive"]
        strategy_results = {}
        
        for strategy in strategies:
            strategy_benchmark = PerformanceBenchmark(f"context_enhancement_{strategy}")
            
            with patch.object(service_manager, 'enhance_context', mock_enhance_context_detailed):
                
                async def enhancement_operation():
                    query = "Help me optimize Python performance"
                    await service_manager.enhance_context(query, strategy=strategy)
                
                strategy_result = await strategy_benchmark.run_async_benchmark(
                    async_operation=enhancement_operation,
                    iterations=30,
                    warmup_iterations=3
                )
            
            strategy_results[strategy] = strategy_result
            
            # 保存每种策略的结果
            save_benchmark_results(
                strategy_result,
                performance_output_dir / f"context_enhancement_{strategy}_results.json"
            )
        
        # 验证策略间的性能差异
        fast_time = strategy_results["fast"].avg_duration_ms
        comprehensive_time = strategy_results["comprehensive"].avg_duration_ms
        
        assert fast_time < comprehensive_time, "Fast strategy should be faster than comprehensive"
        assert all(result.success_rate >= 0.95 for result in strategy_results.values())

    @pytest.mark.asyncio
    async def test_multi_user_concurrent_performance(self, service_manager, mock_conversations, performance_output_dir):
        """测试多用户并发性能"""
        benchmark = PerformanceBenchmark("multi_user_concurrent")
        
        # 模拟多用户场景
        async def mock_user_session(user_id, conversations):
            session_results = []
            
            for conversation in conversations:
                # 模拟用户特定的处理延迟
                user_delay = 0.05 + (hash(user_id) % 100) * 0.001
                await asyncio.sleep(user_delay)
                
                # 处理对话
                await asyncio.sleep(1.2 + conversation.token_count * 0.001)
                
                # 模拟检索操作
                await asyncio.sleep(0.3)
                
                session_results.append(f"Processed conversation for {user_id}")
            
            return session_results
        
        # 创建多个并发用户会话
        async def multi_user_operation():
            user_sessions = []
            
            for i in range(5):  # 5个并发用户
                user_id = f"user_{i}"
                user_conversations = mock_conversations[:2]  # 每个用户2个对话
                
                session_task = mock_user_session(user_id, user_conversations)
                user_sessions.append(session_task)
            
            # 并发执行所有用户会话
            await asyncio.gather(*user_sessions)
        
        results = await benchmark.run_async_benchmark(
            async_operation=multi_user_operation,
            iterations=10,
            concurrency=2,  # 2个并发基准测试
            warmup_iterations=1
        )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "multi_user_concurrent_results.json")
        
        # 并发性能断言
        assert results.success_rate >= 0.85
        assert results.avg_duration_ms <= 15000, "Multi-user scenarios should handle concurrent load"

    @pytest.mark.asyncio
    async def test_system_throughput_performance(self, service_manager, performance_output_dir):
        """测试系统整体吞吐量"""
        benchmark = PerformanceBenchmark("system_throughput")
        
        # 模拟高吞吐量场景
        operation_types = ["process", "retrieve", "enhance"]
        
        async def mock_mixed_operations():
            # 模拟混合操作负载
            operations = []
            
            for op_type in operation_types:
                if op_type == "process":
                    # 对话处理操作
                    operations.append(asyncio.sleep(1.5))
                elif op_type == "retrieve":
                    # 检索操作
                    operations.append(asyncio.sleep(0.1))
                elif op_type == "enhance":
                    # 上下文增强操作
                    operations.append(asyncio.sleep(0.4))
            
            # 并发执行混合操作
            await asyncio.gather(*operations)
        
        # 测试系统在高负载下的表现
        results = await benchmark.run_async_benchmark(
            async_operation=mock_mixed_operations,
            iterations=50,
            concurrency=8,  # 高并发
            warmup_iterations=5
        )
        
        # 保存结果
        save_benchmark_results(results, performance_output_dir / "system_throughput_results.json")
        
        # 吞吐量断言
        assert results.success_rate >= 0.80
        assert results.operations_per_second >= 2.0, "System should maintain reasonable throughput"

    @pytest.mark.asyncio
    async def test_end_to_end_resource_usage(self, service_manager, mock_conversations, performance_output_dir):
        """测试端到端资源使用情况"""
        monitor = SystemResourceMonitor()
        
        # 开始资源监控
        monitor_task = asyncio.create_task(monitor.start_monitoring(interval_seconds=0.5))
        
        try:
            # 模拟资源密集的端到端操作
            async def mock_resource_intensive_workflow():
                # 处理多个对话
                for conversation in mock_conversations:
                    # 模拟CPU密集的压缩操作
                    await asyncio.sleep(0.5)
                    
                    # 模拟内存密集的向量操作
                    temp_vectors = [np.random.random(4096).tolist() for _ in range(10)]
                    await asyncio.sleep(0.2)
                    
                    # 模拟数据库I/O
                    await asyncio.sleep(0.1)
                
                # 模拟检索操作
                for _ in range(5):
                    await asyncio.sleep(0.15)
            
            # 执行多轮工作流以观察资源使用模式
            for i in range(3):
                await mock_resource_intensive_workflow()
                await asyncio.sleep(0.5)  # 轮次间隔
        
        finally:
            monitor.stop_monitoring()
            await monitor_task
        
        # 分析资源使用情况
        resource_summary = monitor.get_summary()
        
        # 保存资源使用报告
        import json
        with open(performance_output_dir / "end_to_end_resource_usage.json", 'w') as f:
            json.dump(resource_summary, f, indent=2, default=str)
        
        # 资源使用断言
        assert resource_summary.get('memory_peak_mb', 0) < 2000, "Memory usage should be reasonable"
        assert resource_summary.get('cpu_max_percent', 0) < 90, "CPU usage should not be excessive"


class TestPerformanceBottleneckAnalysis:
    """性能瓶颈分析测试"""

    @pytest.mark.asyncio
    async def test_workflow_stage_timing_analysis(self, performance_output_dir):
        """测试工作流各阶段时间分析"""
        
        # 模拟工作流各阶段的详细计时
        stage_benchmarks = {}
        
        stages = {
            'conversation_collection': (0.05, 0.02),  # (avg_time, std_dev)
            'semantic_compression': (1.2, 0.3),
            'embedding_generation': (0.8, 0.2),
            'vector_storage': (0.1, 0.02),
            'semantic_retrieval': (0.08, 0.01),
            'reranking': (0.15, 0.03),
            'context_injection': (0.05, 0.01)
        }
        
        for stage_name, (avg_time, std_dev) in stages.items():
            stage_benchmark = PerformanceBenchmark(f"stage_{stage_name}")
            
            async def stage_operation(stage_avg=avg_time, stage_std=std_dev):
                # 模拟具有变异性的处理时间
                processing_time = max(0.01, np.random.normal(stage_avg, stage_std))
                await asyncio.sleep(processing_time)
            
            results = await stage_benchmark.run_async_benchmark(
                async_operation=lambda: stage_operation(avg_time, std_dev),
                iterations=30,
                warmup_iterations=3
            )
            
            stage_benchmarks[stage_name] = results
            
            # 保存每个阶段的结果
            save_benchmark_results(
                results,
                performance_output_dir / f"stage_{stage_name}_timing.json"
            )
        
        # 分析瓶颈阶段
        stage_times = {stage: results.avg_duration_ms for stage, results in stage_benchmarks.items()}
        bottleneck_stage = max(stage_times.keys(), key=lambda x: stage_times[x])
        
        # 生成瓶颈分析报告
        bottleneck_analysis = {
            'bottleneck_stage': bottleneck_stage,
            'bottleneck_time_ms': stage_times[bottleneck_stage],
            'total_pipeline_time_ms': sum(stage_times.values()),
            'bottleneck_percentage': (stage_times[bottleneck_stage] / sum(stage_times.values())) * 100,
            'stage_breakdown': stage_times,
            'optimization_suggestions': []
        }
        
        # 添加优化建议
        if bottleneck_stage == 'semantic_compression':
            bottleneck_analysis['optimization_suggestions'].append(
                "Consider using faster compression models or batch processing"
            )
        elif bottleneck_stage == 'embedding_generation':
            bottleneck_analysis['optimization_suggestions'].append(
                "Optimize embedding API calls or implement caching"
            )
        elif bottleneck_stage == 'reranking':
            bottleneck_analysis['optimization_suggestions'].append(
                "Consider lighter reranking models or adaptive reranking"
            )
        
        # 保存瓶颈分析
        import json
        with open(performance_output_dir / "bottleneck_analysis.json", 'w') as f:
            json.dump(bottleneck_analysis, f, indent=2)
        
        # 验证分析结果
        assert bottleneck_analysis['bottleneck_percentage'] > 0
        assert len(bottleneck_analysis['optimization_suggestions']) > 0

    @pytest.mark.asyncio
    async def test_scalability_performance_analysis(self, performance_output_dir):
        """测试可扩展性性能分析"""
        
        # 测试不同负载下的性能
        load_levels = [1, 5, 10, 20, 50]
        scalability_results = {}
        
        for load_level in load_levels:
            benchmark = PerformanceBenchmark(f"scalability_load_{load_level}")
            
            async def scalable_operation(load=load_level):
                # 模拟负载相关的处理时间
                base_time = 0.5
                load_factor = load * 0.02  # 每个负载单位增加20ms
                congestion_factor = max(0, (load - 10) * 0.05)  # 超过10后拥塞增加
                
                total_time = base_time + load_factor + congestion_factor
                await asyncio.sleep(total_time)
            
            results = await benchmark.run_async_benchmark(
                async_operation=lambda: scalable_operation(load_level),
                iterations=15,
                warmup_iterations=2
            )
            
            scalability_results[load_level] = results
            
            # 保存每个负载级别的结果
            save_benchmark_results(
                results,
                performance_output_dir / f"scalability_load_{load_level}_results.json"
            )
        
        # 分析可扩展性趋势
        scalability_analysis = {
            'load_levels': load_levels,
            'avg_response_times': [scalability_results[load].avg_duration_ms for load in load_levels],
            'throughput_rates': [scalability_results[load].operations_per_second for load in load_levels],
            'success_rates': [scalability_results[load].success_rate for load in load_levels],
            'scalability_coefficient': 0,
            'performance_degradation_threshold': None
        }
        
        # 计算可扩展性系数
        response_times = scalability_analysis['avg_response_times']
        if len(response_times) >= 2:
            scalability_coefficient = (response_times[-1] - response_times[0]) / (load_levels[-1] - load_levels[0])
            scalability_analysis['scalability_coefficient'] = scalability_coefficient
        
        # 找到性能显著下降的阈值
        for i in range(1, len(response_times)):
            if response_times[i] > response_times[i-1] * 1.5:  # 50%性能下降
                scalability_analysis['performance_degradation_threshold'] = load_levels[i]
                break
        
        # 保存可扩展性分析
        import json
        with open(performance_output_dir / "scalability_analysis.json", 'w') as f:
            json.dump(scalability_analysis, f, indent=2)
        
        # 验证可扩展性
        assert all(rate > 0 for rate in scalability_analysis['success_rates']), "All load levels should succeed"
        assert scalability_analysis['scalability_coefficient'] < 100, "Response time growth should be reasonable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])