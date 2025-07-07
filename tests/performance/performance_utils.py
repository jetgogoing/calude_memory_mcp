"""
Claude Memory MCP 服务 - 性能测试工具

提供性能测试的通用工具和基准设施。
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from statistics import mean, median, stdev
from contextlib import asynccontextmanager

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    
    operation: str
    duration_ms: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class BenchmarkResults:
    """基准测试结果"""
    
    test_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration_ms: float
    avg_duration_ms: float
    median_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    std_duration_ms: float
    operations_per_second: float
    success_rate: float
    error_messages: List[str]
    start_time: datetime
    end_time: datetime
    metadata: Dict[str, Any]


class PerformanceTimer:
    """性能计时器上下文管理器"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        
        if exc_type is not None:
            logger.warning(
                "Performance timer completed with exception",
                operation=self.operation_name,
                duration_ms=self.duration_ms,
                exception_type=exc_type.__name__,
                exception_message=str(exc_val)
            )
        else:
            logger.debug(
                "Performance timer completed",
                operation=self.operation_name,
                duration_ms=self.duration_ms
            )


@asynccontextmanager
async def async_performance_timer(operation_name: str):
    """异步性能计时器"""
    start_time = time.time()
    try:
        yield start_time
    finally:
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        logger.debug(
            "Async performance timer completed",
            operation=operation_name,
            duration_ms=duration_ms
        )


class PerformanceBenchmark:
    """性能基准测试管理器"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.metrics: List[PerformanceMetrics] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
    def start_benchmark(self):
        """开始基准测试"""
        self.start_time = datetime.now()
        self.metrics.clear()
        logger.info("Performance benchmark started", test_name=self.test_name)
    
    def end_benchmark(self):
        """结束基准测试"""
        self.end_time = datetime.now()
        logger.info(
            "Performance benchmark completed",
            test_name=self.test_name,
            duration=str(self.end_time - self.start_time),
            total_metrics=len(self.metrics)
        )
    
    def add_metric(self, metric: PerformanceMetrics):
        """添加性能指标"""
        self.metrics.append(metric)
    
    def get_results(self) -> BenchmarkResults:
        """获取基准测试结果"""
        if not self.metrics:
            raise ValueError("No metrics available for benchmark results")
        
        successful_metrics = [m for m in self.metrics if m.success]
        failed_metrics = [m for m in self.metrics if not m.success]
        
        durations = [m.duration_ms for m in successful_metrics]
        
        if durations:
            avg_duration = mean(durations)
            median_duration = median(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            std_duration = stdev(durations) if len(durations) > 1 else 0.0
        else:
            avg_duration = median_duration = min_duration = max_duration = std_duration = 0.0
        
        total_duration = (self.end_time - self.start_time).total_seconds() * 1000
        ops_per_second = len(successful_metrics) / (total_duration / 1000) if total_duration > 0 else 0
        
        return BenchmarkResults(
            test_name=self.test_name,
            total_operations=len(self.metrics),
            successful_operations=len(successful_metrics),
            failed_operations=len(failed_metrics),
            total_duration_ms=total_duration,
            avg_duration_ms=avg_duration,
            median_duration_ms=median_duration,
            min_duration_ms=min_duration,
            max_duration_ms=max_duration,
            std_duration_ms=std_duration,
            operations_per_second=ops_per_second,
            success_rate=len(successful_metrics) / len(self.metrics) if self.metrics else 0,
            error_messages=[m.error_message for m in failed_metrics if m.error_message],
            start_time=self.start_time,
            end_time=self.end_time,
            metadata={}
        )
    
    async def run_async_benchmark(
        self,
        async_operation: Callable,
        iterations: int,
        concurrency: int = 1,
        warmup_iterations: int = 0,
        operation_kwargs: Dict[str, Any] = None
    ) -> BenchmarkResults:
        """运行异步基准测试"""
        if operation_kwargs is None:
            operation_kwargs = {}
        
        self.start_benchmark()
        
        # 预热阶段
        if warmup_iterations > 0:
            logger.info("Running warmup iterations", count=warmup_iterations)
            warmup_tasks = []
            for _ in range(warmup_iterations):
                warmup_tasks.append(async_operation(**operation_kwargs))
            await asyncio.gather(*warmup_tasks, return_exceptions=True)
        
        # 实际基准测试
        semaphore = asyncio.Semaphore(concurrency)
        
        async def run_single_operation():
            async with semaphore:
                start_time = time.time()
                success = True
                error_message = None
                
                try:
                    await async_operation(**operation_kwargs)
                except Exception as e:
                    success = False
                    error_message = str(e)
                    logger.warning(
                        "Benchmark operation failed",
                        test_name=self.test_name,
                        error=error_message
                    )
                
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                metric = PerformanceMetrics(
                    operation=self.test_name,
                    duration_ms=duration_ms,
                    success=success,
                    error_message=error_message
                )
                self.add_metric(metric)
        
        # 并发运行所有操作
        tasks = [run_single_operation() for _ in range(iterations)]
        await asyncio.gather(*tasks)
        
        self.end_benchmark()
        return self.get_results()


class SystemResourceMonitor:
    """系统资源监控器"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics: List[Dict[str, Any]] = []
    
    async def start_monitoring(self, interval_seconds: float = 1.0):
        """开始监控系统资源"""
        self.monitoring = True
        self.metrics.clear()
        
        while self.monitoring:
            try:
                # 获取内存使用情况
                import psutil
                process = psutil.Process()
                
                memory_info = process.memory_info()
                cpu_percent = process.cpu_percent()
                
                metric = {
                    'timestamp': datetime.now(),
                    'memory_rss_mb': memory_info.rss / 1024 / 1024,
                    'memory_vms_mb': memory_info.vms / 1024 / 1024,
                    'cpu_percent': cpu_percent,
                    'num_threads': process.num_threads(),
                }
                
                self.metrics.append(metric)
                
            except Exception as e:
                logger.warning("Failed to collect system metrics", error=str(e))
            
            await asyncio.sleep(interval_seconds)
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
    
    def get_summary(self) -> Dict[str, Any]:
        """获取资源使用摘要"""
        if not self.metrics:
            return {}
        
        memory_values = [m['memory_rss_mb'] for m in self.metrics]
        cpu_values = [m['cpu_percent'] for m in self.metrics if m['cpu_percent'] > 0]
        
        return {
            'duration_seconds': (self.metrics[-1]['timestamp'] - self.metrics[0]['timestamp']).total_seconds(),
            'samples_count': len(self.metrics),
            'memory_peak_mb': max(memory_values) if memory_values else 0,
            'memory_avg_mb': mean(memory_values) if memory_values else 0,
            'cpu_avg_percent': mean(cpu_values) if cpu_values else 0,
            'cpu_max_percent': max(cpu_values) if cpu_values else 0,
        }


def create_test_dataset(size: int, content_length_range: tuple = (50, 500)) -> List[str]:
    """创建测试数据集"""
    import random
    import string
    
    dataset = []
    words = ['python', 'programming', 'claude', 'ai', 'machine', 'learning', 'data', 'science',
             'algorithm', 'function', 'variable', 'class', 'method', 'object', 'array', 'list',
             'dictionary', 'string', 'integer', 'boolean', 'loop', 'condition', 'exception',
             'import', 'module', 'library', 'framework', 'database', 'query', 'api']
    
    for i in range(size):
        min_length, max_length = content_length_range
        target_length = random.randint(min_length, max_length)
        
        content = []
        current_length = 0
        
        while current_length < target_length:
            word = random.choice(words)
            if current_length + len(word) + 1 <= target_length:
                content.append(word)
                current_length += len(word) + 1
            else:
                break
        
        # 添加一些随机标点和结构
        text = ' '.join(content)
        if random.random() < 0.3:
            text = f"How to {text}?"
        elif random.random() < 0.3:
            text = f"I need help with {text}."
        elif random.random() < 0.3:
            text = f"Can you explain {text}?"
        
        dataset.append(text)
    
    return dataset


def save_benchmark_results(results: BenchmarkResults, output_path: Path):
    """保存基准测试结果到文件"""
    results_dict = asdict(results)
    
    # 转换datetime对象为字符串
    results_dict['start_time'] = results.start_time.isoformat()
    results_dict['end_time'] = results.end_time.isoformat()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results_dict, f, indent=2, ensure_ascii=False)
    
    logger.info("Benchmark results saved", output_path=str(output_path))


def load_benchmark_results(input_path: Path) -> BenchmarkResults:
    """从文件加载基准测试结果"""
    with open(input_path, 'r', encoding='utf-8') as f:
        results_dict = json.load(f)
    
    # 转换字符串为datetime对象
    results_dict['start_time'] = datetime.fromisoformat(results_dict['start_time'])
    results_dict['end_time'] = datetime.fromisoformat(results_dict['end_time'])
    
    return BenchmarkResults(**results_dict)


def compare_benchmark_results(baseline: BenchmarkResults, current: BenchmarkResults) -> Dict[str, Any]:
    """比较两个基准测试结果"""
    comparison = {
        'test_name': current.test_name,
        'baseline_ops_per_second': baseline.operations_per_second,
        'current_ops_per_second': current.operations_per_second,
        'throughput_change_percent': 0,
        'baseline_avg_duration_ms': baseline.avg_duration_ms,
        'current_avg_duration_ms': current.avg_duration_ms,
        'latency_change_percent': 0,
        'baseline_success_rate': baseline.success_rate,
        'current_success_rate': current.success_rate,
        'success_rate_change': 0,
        'performance_trend': 'stable'
    }
    
    # 计算吞吐量变化
    if baseline.operations_per_second > 0:
        comparison['throughput_change_percent'] = (
            (current.operations_per_second - baseline.operations_per_second) / 
            baseline.operations_per_second * 100
        )
    
    # 计算延迟变化
    if baseline.avg_duration_ms > 0:
        comparison['latency_change_percent'] = (
            (current.avg_duration_ms - baseline.avg_duration_ms) / 
            baseline.avg_duration_ms * 100
        )
    
    # 计算成功率变化
    comparison['success_rate_change'] = current.success_rate - baseline.success_rate
    
    # 确定性能趋势
    throughput_change = comparison['throughput_change_percent']
    latency_change = comparison['latency_change_percent']
    
    if throughput_change > 10 and latency_change < -10:
        comparison['performance_trend'] = 'improved'
    elif throughput_change < -10 or latency_change > 20:
        comparison['performance_trend'] = 'degraded'
    elif abs(throughput_change) <= 5 and abs(latency_change) <= 5:
        comparison['performance_trend'] = 'stable'
    else:
        comparison['performance_trend'] = 'mixed'
    
    return comparison


# 性能阈值配置
PERFORMANCE_THRESHOLDS = {
    'embedding_generation': {
        'max_avg_duration_ms': 2000,  # 2秒
        'min_ops_per_second': 0.5,
        'min_success_rate': 0.95
    },
    'semantic_retrieval': {
        'max_avg_duration_ms': 150,   # 150ms
        'min_ops_per_second': 6.0,
        'min_success_rate': 0.98
    },
    'conversation_compression': {
        'max_avg_duration_ms': 5000,  # 5秒
        'min_ops_per_second': 0.2,
        'min_success_rate': 0.90
    },
    'context_injection': {
        'max_avg_duration_ms': 300,   # 300ms
        'min_ops_per_second': 3.0,
        'min_success_rate': 0.95
    },
    'end_to_end_workflow': {
        'max_avg_duration_ms': 8000,  # 8秒
        'min_ops_per_second': 0.1,
        'min_success_rate': 0.85
    }
}


def check_performance_thresholds(results: BenchmarkResults) -> Dict[str, bool]:
    """检查性能是否符合阈值要求"""
    test_type = results.test_name.lower().replace(' ', '_').replace('-', '_')
    thresholds = PERFORMANCE_THRESHOLDS.get(test_type, {})
    
    if not thresholds:
        logger.warning("No thresholds defined for test type", test_type=test_type)
        return {'unknown_test_type': False}
    
    checks = {}
    
    # 检查平均延迟
    if 'max_avg_duration_ms' in thresholds:
        checks['avg_duration_ok'] = results.avg_duration_ms <= thresholds['max_avg_duration_ms']
    
    # 检查吞吐量
    if 'min_ops_per_second' in thresholds:
        checks['throughput_ok'] = results.operations_per_second >= thresholds['min_ops_per_second']
    
    # 检查成功率
    if 'min_success_rate' in thresholds:
        checks['success_rate_ok'] = results.success_rate >= thresholds['min_success_rate']
    
    checks['all_checks_passed'] = all(checks.values())
    
    return checks