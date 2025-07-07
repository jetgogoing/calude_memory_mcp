"""
Claude Memory MCP 服务 - 资源限制处理测试

测试内容：
- 内存使用限制和管理
- CPU使用监控和限制
- 磁盘空间管理
- 文件描述符限制处理
- 并发连接数限制
- 资源泄漏检测和恢复
"""

import asyncio
import time
import psutil
import threading
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import tempfile
import os

import pytest

from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType
from claude_memory.config.settings import get_settings


@pytest.fixture
def mock_settings():
    """模拟资源限制配置"""
    settings = Mock()
    
    # 资源限制设置
    settings.resources.max_memory_mb = 512
    settings.resources.max_cpu_percent = 80
    settings.resources.max_disk_usage_mb = 1024
    settings.resources.max_concurrent_operations = 10
    settings.resources.max_file_descriptors = 100
    
    # 监控设置
    settings.monitoring.enable_resource_monitoring = True
    settings.monitoring.monitoring_interval_seconds = 1
    settings.monitoring.alert_thresholds = {
        "memory_mb": 400,
        "cpu_percent": 70,
        "disk_mb": 800
    }
    
    # 清理设置
    settings.cleanup.enable_automatic_cleanup = True
    settings.cleanup.cleanup_interval_minutes = 5
    settings.cleanup.temp_file_max_age_hours = 1
    
    return settings


class TestMemoryLimits:
    """内存限制测试"""

    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self, mock_settings):
        """测试内存使用监控"""
        
        class MemoryMonitor:
            def __init__(self, max_memory_mb=512):
                self.max_memory_mb = max_memory_mb
                self.current_usage_mb = 0
                self.allocated_objects = []
            
            def allocate_memory(self, size_mb):
                if self.current_usage_mb + size_mb > self.max_memory_mb:
                    raise MemoryError(f"Memory limit exceeded: {self.current_usage_mb + size_mb}MB > {self.max_memory_mb}MB")
                
                # 模拟内存分配
                mock_object = {"data": "x" * (size_mb * 1024 * 1024)}
                self.allocated_objects.append(mock_object)
                self.current_usage_mb += size_mb
                return len(self.allocated_objects) - 1
            
            def deallocate_memory(self, object_id):
                if 0 <= object_id < len(self.allocated_objects):
                    obj = self.allocated_objects[object_id]
                    if obj is not None:
                        size_mb = len(obj["data"]) // (1024 * 1024)
                        self.current_usage_mb -= size_mb
                        self.allocated_objects[object_id] = None
            
            def get_memory_usage(self):
                return {
                    "current_mb": self.current_usage_mb,
                    "max_mb": self.max_memory_mb,
                    "usage_percent": (self.current_usage_mb / self.max_memory_mb) * 100,
                    "available_mb": self.max_memory_mb - self.current_usage_mb
                }
        
        # 测试内存监控
        monitor = MemoryMonitor(max_memory_mb=100)
        
        # 正常分配
        obj1 = monitor.allocate_memory(30)
        obj2 = monitor.allocate_memory(40)
        
        usage = monitor.get_memory_usage()
        assert usage["current_mb"] == 70
        assert usage["usage_percent"] == 70.0
        
        # 尝试超限分配
        with pytest.raises(MemoryError):
            monitor.allocate_memory(50)  # 70 + 50 > 100
        
        # 释放内存
        monitor.deallocate_memory(obj1)
        usage_after_dealloc = monitor.get_memory_usage()
        assert usage_after_dealloc["current_mb"] == 40

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, mock_settings):
        """测试内存压力处理"""
        
        class MemoryPressureHandler:
            def __init__(self, warning_threshold=0.7, critical_threshold=0.9):
                self.warning_threshold = warning_threshold
                self.critical_threshold = critical_threshold
                self.cache = {}
                self.temp_buffers = []
            
            def get_memory_pressure_level(self, usage_percent):
                if usage_percent >= self.critical_threshold * 100:
                    return "CRITICAL"
                elif usage_percent >= self.warning_threshold * 100:
                    return "WARNING"
                return "NORMAL"
            
            async def handle_memory_pressure(self, usage_percent):
                pressure_level = self.get_memory_pressure_level(usage_percent)
                
                if pressure_level == "WARNING":
                    # 清理缓存
                    cache_cleared = len(self.cache)
                    self.cache.clear()
                    return f"Cleared cache: {cache_cleared} items"
                
                elif pressure_level == "CRITICAL":
                    # 清理所有可清理的资源
                    cache_cleared = len(self.cache)
                    buffers_cleared = len(self.temp_buffers)
                    
                    self.cache.clear()
                    self.temp_buffers.clear()
                    
                    return f"Emergency cleanup: {cache_cleared} cache items, {buffers_cleared} buffers"
                
                return "No action needed"
            
            def add_cache_item(self, key, value):
                self.cache[key] = value
            
            def add_temp_buffer(self, buffer):
                self.temp_buffers.append(buffer)
        
        # 测试内存压力处理
        handler = MemoryPressureHandler()
        
        # 添加一些数据
        for i in range(10):
            handler.add_cache_item(f"key_{i}", f"value_{i}")
            handler.add_temp_buffer(f"buffer_{i}")
        
        # 测试警告级别处理
        result_warning = await handler.handle_memory_pressure(75)
        assert "Cleared cache" in result_warning
        assert len(handler.cache) == 0
        assert len(handler.temp_buffers) == 10  # 缓冲区未清理
        
        # 重新添加数据
        for i in range(5):
            handler.add_cache_item(f"key_{i}", f"value_{i}")
        
        # 测试临界级别处理
        result_critical = await handler.handle_memory_pressure(95)
        assert "Emergency cleanup" in result_critical
        assert len(handler.cache) == 0
        assert len(handler.temp_buffers) == 0

    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, mock_settings):
        """测试内存泄漏检测"""
        
        class MemoryLeakDetector:
            def __init__(self):
                self.memory_snapshots = []
                self.object_registry = {}
                self.next_object_id = 0
            
            def register_object(self, obj_type, size_estimate=1):
                obj_id = self.next_object_id
                self.next_object_id += 1
                
                self.object_registry[obj_id] = {
                    "type": obj_type,
                    "size": size_estimate,
                    "created_at": time.time()
                }
                return obj_id
            
            def unregister_object(self, obj_id):
                if obj_id in self.object_registry:
                    del self.object_registry[obj_id]
            
            def take_memory_snapshot(self):
                current_time = time.time()
                total_objects = len(self.object_registry)
                total_size = sum(obj["size"] for obj in self.object_registry.values())
                
                snapshot = {
                    "timestamp": current_time,
                    "total_objects": total_objects,
                    "total_size": total_size,
                    "objects_by_type": {}
                }
                
                # 按类型统计对象
                for obj_info in self.object_registry.values():
                    obj_type = obj_info["type"]
                    if obj_type not in snapshot["objects_by_type"]:
                        snapshot["objects_by_type"][obj_type] = 0
                    snapshot["objects_by_type"][obj_type] += 1
                
                self.memory_snapshots.append(snapshot)
                return snapshot
            
            def detect_potential_leaks(self, min_snapshots=3):
                if len(self.memory_snapshots) < min_snapshots:
                    return {"status": "insufficient_data"}
                
                # 分析最近的快照
                recent_snapshots = self.memory_snapshots[-min_snapshots:]
                
                # 检查内存使用趋势
                sizes = [s["total_size"] for s in recent_snapshots]
                object_counts = [s["total_objects"] for s in recent_snapshots]
                
                # 简单的增长检测
                size_trend = "increasing" if sizes[-1] > sizes[0] * 1.5 else "stable"
                count_trend = "increasing" if object_counts[-1] > object_counts[0] * 1.5 else "stable"
                
                potential_leaks = []
                if size_trend == "increasing" or count_trend == "increasing":
                    # 找出持续增长的对象类型
                    for obj_type in recent_snapshots[-1]["objects_by_type"]:
                        type_counts = [s["objects_by_type"].get(obj_type, 0) for s in recent_snapshots]
                        if type_counts[-1] > type_counts[0] * 2:
                            potential_leaks.append(obj_type)
                
                return {
                    "status": "analysis_complete",
                    "size_trend": size_trend,
                    "count_trend": count_trend,
                    "potential_leak_types": potential_leaks
                }
        
        # 测试内存泄漏检测
        detector = MemoryLeakDetector()
        
        # 模拟正常对象创建和销毁
        obj1 = detector.register_object("buffer", 10)
        obj2 = detector.register_object("cache", 5)
        detector.take_memory_snapshot()
        
        detector.unregister_object(obj1)
        detector.take_memory_snapshot()
        
        # 模拟内存泄漏（创建但不销毁）
        for i in range(10):
            detector.register_object("leaked_object", 2)
        detector.take_memory_snapshot()
        
        # 继续创建更多泄漏对象
        for i in range(15):
            detector.register_object("leaked_object", 2)
        detector.take_memory_snapshot()
        
        # 检测泄漏
        leak_analysis = detector.detect_potential_leaks()
        assert leak_analysis["status"] == "analysis_complete"
        assert "leaked_object" in leak_analysis["potential_leak_types"]


class TestCPULimits:
    """CPU限制测试"""

    @pytest.mark.asyncio
    async def test_cpu_usage_throttling(self, mock_settings):
        """测试CPU使用限制"""
        
        class CPUThrottler:
            def __init__(self, max_cpu_percent=80):
                self.max_cpu_percent = max_cpu_percent
                self.current_tasks = []
                self.throttle_active = False
            
            async def monitor_cpu_usage(self):
                # 模拟CPU使用率监控
                if len(self.current_tasks) > 5:
                    return 85  # 模拟高CPU使用率
                return 30  # 正常使用率
            
            async def execute_with_throttling(self, task_func, task_id):
                # 检查CPU使用率
                cpu_usage = await self.monitor_cpu_usage()
                
                if cpu_usage > self.max_cpu_percent:
                    self.throttle_active = True
                    # 限制并发任务数
                    while len(self.current_tasks) >= 3:
                        await asyncio.sleep(0.1)
                
                # 执行任务
                self.current_tasks.append(task_id)
                try:
                    start_time = time.time()
                    result = await task_func()
                    execution_time = time.time() - start_time
                    
                    # 如果启用了节流，添加延迟
                    if self.throttle_active and execution_time < 0.1:
                        await asyncio.sleep(0.1 - execution_time)
                    
                    return result
                finally:
                    self.current_tasks.remove(task_id)
        
        # 测试CPU限制
        throttler = CPUThrottler(max_cpu_percent=80)
        
        # 模拟CPU密集任务
        async def cpu_intensive_task():
            # 模拟计算
            await asyncio.sleep(0.05)
            return "task_completed"
        
        # 执行多个任务以触发限制
        tasks = []
        for i in range(8):
            task = throttler.execute_with_throttling(cpu_intensive_task, f"task_{i}")
            tasks.append(task)
        
        # 执行所有任务
        results = await asyncio.gather(*tasks)
        
        # 验证所有任务完成
        assert len(results) == 8
        assert all(result == "task_completed" for result in results)
        
        # 验证节流机制被激活
        assert throttler.throttle_active is True

    @pytest.mark.asyncio
    async def test_background_task_priority(self, mock_settings):
        """测试后台任务优先级管理"""
        
        class TaskPriorityManager:
            def __init__(self):
                self.high_priority_queue = asyncio.Queue()
                self.normal_priority_queue = asyncio.Queue()
                self.low_priority_queue = asyncio.Queue()
                self.running = False
            
            async def add_task(self, task_func, priority="normal"):
                task_item = {
                    "func": task_func,
                    "created_at": time.time()
                }
                
                if priority == "high":
                    await self.high_priority_queue.put(task_item)
                elif priority == "low":
                    await self.low_priority_queue.put(task_item)
                else:
                    await self.normal_priority_queue.put(task_item)
            
            async def process_tasks(self, max_concurrent=3):
                self.running = True
                active_tasks = set()
                processed_tasks = []
                
                try:
                    while self.running:
                        # 限制并发数
                        if len(active_tasks) >= max_concurrent:
                            # 等待一些任务完成
                            done, active_tasks = await asyncio.wait(
                                active_tasks, 
                                return_when=asyncio.FIRST_COMPLETED,
                                timeout=0.1
                            )
                            
                            for task in done:
                                result = await task
                                processed_tasks.append(result)
                        
                        # 按优先级获取任务
                        task_item = None
                        priority = None
                        
                        try:
                            task_item = self.high_priority_queue.get_nowait()
                            priority = "high"
                        except asyncio.QueueEmpty:
                            try:
                                task_item = self.normal_priority_queue.get_nowait()
                                priority = "normal"
                            except asyncio.QueueEmpty:
                                try:
                                    task_item = self.low_priority_queue.get_nowait()
                                    priority = "low"
                                except asyncio.QueueEmpty:
                                    # 没有任务，短暂等待
                                    await asyncio.sleep(0.01)
                                    continue
                        
                        if task_item:
                            # 启动任务
                            task_coroutine = self._execute_task(task_item, priority)
                            active_tasks.add(asyncio.create_task(task_coroutine))
                
                except Exception:
                    pass
                
                # 等待剩余任务完成
                if active_tasks:
                    done_tasks = await asyncio.gather(*active_tasks, return_exceptions=True)
                    processed_tasks.extend(done_tasks)
                
                return processed_tasks
            
            async def _execute_task(self, task_item, priority):
                start_time = time.time()
                try:
                    result = await task_item["func"]()
                    execution_time = time.time() - start_time
                    return {
                        "result": result,
                        "priority": priority,
                        "execution_time": execution_time,
                        "queue_time": start_time - task_item["created_at"]
                    }
                except Exception as e:
                    return {
                        "error": str(e),
                        "priority": priority
                    }
            
            def stop(self):
                self.running = False
        
        # 测试任务优先级管理
        manager = TaskPriorityManager()
        
        # 添加不同优先级的任务
        async def quick_task(name):
            await asyncio.sleep(0.05)
            return f"completed_{name}"
        
        # 逆序添加以验证优先级
        await manager.add_task(lambda: quick_task("low1"), "low")
        await manager.add_task(lambda: quick_task("normal1"), "normal")
        await manager.add_task(lambda: quick_task("high1"), "high")
        await manager.add_task(lambda: quick_task("low2"), "low")
        await manager.add_task(lambda: quick_task("high2"), "high")
        
        # 启动处理器并快速停止
        async def run_processor():
            await asyncio.sleep(0.3)  # 让任务有时间执行
            manager.stop()
        
        # 并发运行处理器和停止器
        processor_task = asyncio.create_task(manager.process_tasks(max_concurrent=2))
        stopper_task = asyncio.create_task(run_processor())
        
        await stopper_task
        results = await processor_task
        
        # 验证高优先级任务先执行
        high_priority_results = [r for r in results if isinstance(r, dict) and r.get("priority") == "high"]
        assert len(high_priority_results) >= 2


class TestDiskSpaceLimits:
    """磁盘空间限制测试"""

    @pytest.mark.asyncio
    async def test_disk_usage_monitoring(self, mock_settings):
        """测试磁盘使用监控"""
        
        class DiskSpaceManager:
            def __init__(self, temp_dir, max_size_mb=100):
                self.temp_dir = temp_dir
                self.max_size_mb = max_size_mb
                self.managed_files = []
            
            def get_directory_size_mb(self):
                total_size = 0
                for root, dirs, files in os.walk(self.temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
                return total_size / (1024 * 1024)  # 转换为MB
            
            async def create_temp_file(self, filename, size_mb):
                current_size = self.get_directory_size_mb()
                
                if current_size + size_mb > self.max_size_mb:
                    raise Exception(f"Disk space limit exceeded: {current_size + size_mb}MB > {self.max_size_mb}MB")
                
                file_path = os.path.join(self.temp_dir, filename)
                
                # 创建指定大小的文件
                with open(file_path, 'wb') as f:
                    f.write(b'0' * int(size_mb * 1024 * 1024))
                
                self.managed_files.append(file_path)
                return file_path
            
            async def cleanup_old_files(self, max_age_seconds=3600):
                current_time = time.time()
                removed_files = []
                
                for file_path in self.managed_files[:]:
                    if os.path.exists(file_path):
                        file_age = current_time - os.path.getctime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            self.managed_files.remove(file_path)
                            removed_files.append(file_path)
                
                return removed_files
            
            async def emergency_cleanup(self, target_free_mb=20):
                """紧急清理，释放指定大小的空间"""
                current_size = self.get_directory_size_mb()
                target_size = self.max_size_mb - target_free_mb
                
                if current_size <= target_size:
                    return []  # 无需清理
                
                # 按创建时间排序（最旧的先删除）
                files_with_time = []
                for file_path in self.managed_files:
                    if os.path.exists(file_path):
                        ctime = os.path.getctime(file_path)
                        size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        files_with_time.append((ctime, file_path, size_mb))
                
                files_with_time.sort()  # 按时间排序
                
                removed_files = []
                space_freed = 0
                
                for ctime, file_path, size_mb in files_with_time:
                    if current_size - space_freed <= target_size:
                        break
                    
                    os.remove(file_path)
                    self.managed_files.remove(file_path)
                    removed_files.append(file_path)
                    space_freed += size_mb
                
                return removed_files
        
        # 测试磁盘空间管理
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DiskSpaceManager(temp_dir, max_size_mb=10)
            
            # 创建一些文件
            file1 = await manager.create_temp_file("test1.dat", 3)
            file2 = await manager.create_temp_file("test2.dat", 4)
            
            current_usage = manager.get_directory_size_mb()
            assert current_usage >= 7  # 约7MB
            
            # 尝试创建超限文件
            with pytest.raises(Exception, match="Disk space limit exceeded"):
                await manager.create_temp_file("test3.dat", 5)  # 7 + 5 > 10
            
            # 紧急清理
            removed = await manager.emergency_cleanup(target_free_mb=5)
            assert len(removed) > 0
            
            # 验证空间被释放
            new_usage = manager.get_directory_size_mb()
            assert new_usage < current_usage

    @pytest.mark.asyncio
    async def test_temporary_file_lifecycle(self, mock_settings):
        """测试临时文件生命周期管理"""
        
        class TempFileManager:
            def __init__(self, base_dir):
                self.base_dir = base_dir
                self.active_files = {}
                self.file_metadata = {}
            
            async def create_temp_file(self, prefix="temp", suffix=".tmp", ttl_seconds=3600):
                # 生成唯一文件名
                timestamp = int(time.time() * 1000)
                filename = f"{prefix}_{timestamp}{suffix}"
                file_path = os.path.join(self.base_dir, filename)
                
                # 创建文件
                with open(file_path, 'w') as f:
                    f.write(f"Created at {datetime.now()}")
                
                # 记录元数据
                file_id = len(self.active_files)
                self.active_files[file_id] = file_path
                self.file_metadata[file_id] = {
                    "created_at": time.time(),
                    "ttl_seconds": ttl_seconds,
                    "size_bytes": os.path.getsize(file_path)
                }
                
                return file_id
            
            async def cleanup_expired_files(self):
                current_time = time.time()
                expired_files = []
                
                for file_id, metadata in list(self.file_metadata.items()):
                    if current_time - metadata["created_at"] > metadata["ttl_seconds"]:
                        file_path = self.active_files.get(file_id)
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                            expired_files.append(file_path)
                        
                        # 清理记录
                        del self.active_files[file_id]
                        del self.file_metadata[file_id]
                
                return expired_files
            
            async def extend_file_ttl(self, file_id, additional_seconds):
                if file_id in self.file_metadata:
                    self.file_metadata[file_id]["ttl_seconds"] += additional_seconds
                    return True
                return False
            
            def get_active_files_info(self):
                current_time = time.time()
                info = {
                    "total_files": len(self.active_files),
                    "total_size_mb": 0,
                    "files_by_age": {"new": 0, "medium": 0, "old": 0}
                }
                
                for metadata in self.file_metadata.values():
                    info["total_size_mb"] += metadata["size_bytes"] / (1024 * 1024)
                    
                    age = current_time - metadata["created_at"]
                    if age < 300:  # 5分钟
                        info["files_by_age"]["new"] += 1
                    elif age < 1800:  # 30分钟
                        info["files_by_age"]["medium"] += 1
                    else:
                        info["files_by_age"]["old"] += 1
                
                return info
        
        # 测试临时文件管理
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TempFileManager(temp_dir)
            
            # 创建一些临时文件
            file1 = await manager.create_temp_file("test1", ".log", ttl_seconds=1)
            file2 = await manager.create_temp_file("test2", ".dat", ttl_seconds=10)
            
            # 检查活跃文件信息
            info = manager.get_active_files_info()
            assert info["total_files"] == 2
            assert info["files_by_age"]["new"] == 2
            
            # 等待文件过期
            await asyncio.sleep(1.5)
            
            # 清理过期文件
            expired = await manager.cleanup_expired_files()
            assert len(expired) == 1  # file1应该过期
            
            # 验证剩余文件
            info_after_cleanup = manager.get_active_files_info()
            assert info_after_cleanup["total_files"] == 1


class TestConcurrencyLimits:
    """并发限制测试"""

    @pytest.mark.asyncio
    async def test_connection_pool_limits(self, mock_settings):
        """测试连接池限制"""
        
        class ConnectionPool:
            def __init__(self, max_connections=5):
                self.max_connections = max_connections
                self.active_connections = set()
                self.waiting_queue = asyncio.Queue()
                self.connection_counter = 0
            
            async def acquire_connection(self, timeout=5.0):
                if len(self.active_connections) < self.max_connections:
                    # 创建新连接
                    connection_id = f"conn_{self.connection_counter}"
                    self.connection_counter += 1
                    self.active_connections.add(connection_id)
                    return connection_id
                else:
                    # 等待连接可用
                    try:
                        connection_id = await asyncio.wait_for(
                            self.waiting_queue.get(), 
                            timeout=timeout
                        )
                        self.active_connections.add(connection_id)
                        return connection_id
                    except asyncio.TimeoutError:
                        raise Exception("Connection pool timeout")
            
            async def release_connection(self, connection_id):
                if connection_id in self.active_connections:
                    self.active_connections.remove(connection_id)
                    
                    # 如果有等待的请求，立即分配连接
                    if not self.waiting_queue.empty():
                        try:
                            self.waiting_queue.put_nowait(connection_id)
                        except asyncio.QueueFull:
                            pass
            
            def get_pool_stats(self):
                return {
                    "active_connections": len(self.active_connections),
                    "max_connections": self.max_connections,
                    "waiting_requests": self.waiting_queue.qsize(),
                    "utilization": len(self.active_connections) / self.max_connections
                }
        
        # 测试连接池限制
        pool = ConnectionPool(max_connections=3)
        
        # 获取所有可用连接
        conn1 = await pool.acquire_connection()
        conn2 = await pool.acquire_connection()
        conn3 = await pool.acquire_connection()
        
        stats = pool.get_pool_stats()
        assert stats["active_connections"] == 3
        assert stats["utilization"] == 1.0
        
        # 尝试获取第4个连接（应该超时）
        with pytest.raises(Exception, match="Connection pool timeout"):
            await pool.acquire_connection(timeout=0.1)
        
        # 释放一个连接
        await pool.release_connection(conn1)
        
        # 现在应该能获取新连接
        conn4 = await pool.acquire_connection(timeout=0.1)
        assert conn4 is not None

    @pytest.mark.asyncio
    async def test_request_rate_limiting(self, mock_settings):
        """测试请求频率限制"""
        
        class RateLimiter:
            def __init__(self, max_requests=10, time_window_seconds=60):
                self.max_requests = max_requests
                self.time_window = time_window_seconds
                self.request_timestamps = []
            
            async def check_rate_limit(self, client_id="default"):
                current_time = time.time()
                
                # 清理过期的时间戳
                cutoff_time = current_time - self.time_window
                self.request_timestamps = [
                    ts for ts in self.request_timestamps 
                    if ts > cutoff_time
                ]
                
                # 检查是否超过限制
                if len(self.request_timestamps) >= self.max_requests:
                    oldest_request = min(self.request_timestamps)
                    retry_after = self.time_window - (current_time - oldest_request)
                    raise Exception(f"Rate limit exceeded. Retry after {retry_after:.2f} seconds")
                
                # 记录当前请求
                self.request_timestamps.append(current_time)
                return True
            
            def get_rate_limit_status(self):
                current_time = time.time()
                cutoff_time = current_time - self.time_window
                
                valid_requests = [
                    ts for ts in self.request_timestamps 
                    if ts > cutoff_time
                ]
                
                return {
                    "requests_in_window": len(valid_requests),
                    "max_requests": self.max_requests,
                    "requests_remaining": max(0, self.max_requests - len(valid_requests)),
                    "window_resets_in": self.time_window - (current_time - min(valid_requests)) if valid_requests else 0
                }
        
        # 测试频率限制
        limiter = RateLimiter(max_requests=5, time_window_seconds=2)
        
        # 发送请求直到达到限制
        for i in range(5):
            result = await limiter.check_rate_limit()
            assert result is True
        
        # 第6个请求应该被限制
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await limiter.check_rate_limit()
        
        # 检查状态
        status = limiter.get_rate_limit_status()
        assert status["requests_remaining"] == 0
        
        # 等待时间窗口重置
        await asyncio.sleep(2.1)
        
        # 现在应该能再次发送请求
        result = await limiter.check_rate_limit()
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])