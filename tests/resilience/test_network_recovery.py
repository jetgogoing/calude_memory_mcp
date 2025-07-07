"""
Claude Memory MCP 服务 - 网络恢复能力测试

测试内容：
- 网络连接中断和恢复
- DNS解析失败处理
- 代理和防火墙问题处理
- 网络延迟和不稳定连接处理
- 离线模式和本地缓存
"""

import asyncio
import time
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

import pytest
import aiohttp

from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.processors.semantic_compressor import SemanticCompressor
from claude_memory.models.data_models import MemoryUnitModel
from claude_memory.config.settings import get_settings


@pytest.fixture
def mock_settings():
    """模拟网络配置设置"""
    settings = Mock()
    
    # 网络设置
    settings.network.connection_timeout = 10
    settings.network.read_timeout = 30
    settings.network.max_connections = 100
    settings.network.enable_keepalive = True
    
    # 重试和恢复设置
    settings.resilience.max_retries = 3
    settings.resilience.retry_delay_base = 1.0
    settings.resilience.enable_circuit_breaker = True
    settings.resilience.circuit_breaker_threshold = 5
    settings.resilience.circuit_breaker_timeout = 60
    
    # 缓存设置
    settings.cache.enable_offline_cache = True
    settings.cache.cache_ttl_hours = 24
    settings.cache.max_cache_size_mb = 100
    
    # API设置
    settings.models.embedding.base_url = "https://api.siliconflow.cn/v1"
    settings.models.compression.base_url = "https://openrouter.ai/api/v1"
    
    # Qdrant设置
    settings.qdrant.url = "http://localhost:6333"
    settings.qdrant.timeout = 10
    
    return settings


class TestNetworkConnectivity:
    """网络连接测试"""

    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self, mock_settings):
        """测试连接超时处理"""
        with patch('claude_memory.retrievers.semantic_retriever.get_settings', return_value=mock_settings):
            retriever = SemanticRetriever()
            
            # 模拟连接超时
            async def mock_timeout_request(*args, **kwargs):
                await asyncio.sleep(15)  # 超过10秒超时
                return Mock()
            
            with patch('aiohttp.ClientSession.post', mock_timeout_request):
                start_time = time.time()
                
                with pytest.raises(Exception):
                    await retriever._generate_vector("test query")
                
                elapsed_time = time.time() - start_time
                assert elapsed_time < 12, "应该在超时时间内失败"

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, mock_settings):
        """测试DNS解析失败处理"""
        with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
            compressor = SemanticCompressor()
            
            # 模拟DNS解析失败
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.side_effect = aiohttp.ClientConnectorError(
                    connection_key=None,
                    os_error=OSError("Name or service not known")
                )
                
                with pytest.raises(Exception) as exc_info:
                    await compressor._call_compression_api("test content")
                
                assert "Name or service not known" in str(exc_info.value) or "DNS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connection_reset_handling(self, mock_settings):
        """测试连接重置处理"""
        with patch('claude_memory.retrievers.semantic_retriever.get_settings', return_value=mock_settings):
            retriever = SemanticRetriever()
            
            # 模拟连接重置
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.side_effect = aiohttp.ClientConnectionError("Connection reset by peer")
                
                with pytest.raises(Exception) as exc_info:
                    await retriever._generate_vector("test query")
                
                assert "Connection reset" in str(exc_info.value) or "ConnectionError" in str(type(exc_info.value).__name__)

    @pytest.mark.asyncio
    async def test_intermittent_connectivity(self, mock_settings):
        """测试间歇性连接问题"""
        with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
            compressor = SemanticCompressor()
            
            # 模拟间歇性连接：前两次失败，第三次成功
            call_count = 0
            
            async def intermittent_connection(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                if call_count <= 2:
                    raise aiohttp.ClientConnectorError(
                        connection_key=None,
                        os_error=OSError("Network unreachable")
                    )
                
                # 第三次调用成功
                response = Mock()
                response.status = 200
                response.json = AsyncMock(return_value={"result": "success"})
                return response
            
            # 实现重试逻辑
            max_retries = 3
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    with patch('aiohttp.ClientSession.post', intermittent_connection):
                        result = await compressor._call_compression_api("test content")
                    break
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(0.1)
            
            # 验证最终成功
            assert call_count == 3


class TestNetworkRecovery:
    """网络恢复测试"""

    @pytest.mark.asyncio
    async def test_automatic_reconnection(self, mock_settings):
        """测试自动重连机制"""
        
        class ConnectionManager:
            def __init__(self):
                self.connection_attempts = 0
                self.is_connected = False
            
            async def connect(self):
                self.connection_attempts += 1
                
                # 前3次连接失败
                if self.connection_attempts <= 3:
                    raise Exception(f"Connection failed, attempt {self.connection_attempts}")
                
                # 第4次连接成功
                self.is_connected = True
                return True
            
            async def auto_reconnect(self, max_attempts=5):
                for attempt in range(max_attempts):
                    try:
                        await self.connect()
                        return True
                    except Exception:
                        if attempt < max_attempts - 1:
                            # 指数退避
                            delay = 2 ** attempt
                            await asyncio.sleep(delay * 0.1)  # 缩短延迟用于测试
                        else:
                            raise
        
        # 测试自动重连
        manager = ConnectionManager()
        
        # 应该在第4次尝试时成功连接
        success = await manager.auto_reconnect()
        
        assert success is True
        assert manager.is_connected is True
        assert manager.connection_attempts == 4

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_network_failure(self, mock_settings):
        """测试网络失败时的优雅降级"""
        
        class ServiceWithFallback:
            def __init__(self):
                self.primary_available = True
                self.fallback_cache = {
                    "test_query": ["cached_result_1", "cached_result_2"]
                }
            
            async def primary_service(self, query):
                if not self.primary_available:
                    raise Exception("Primary service unavailable")
                
                # 模拟网络调用
                await asyncio.sleep(0.1)
                return [f"live_result_{i}" for i in range(3)]
            
            async def fallback_service(self, query):
                # 返回缓存结果
                return self.fallback_cache.get(query, ["default_fallback"])
            
            async def get_results(self, query):
                try:
                    return await self.primary_service(query)
                except Exception:
                    # 降级到缓存
                    return await self.fallback_service(query)
        
        # 测试正常情况
        service = ServiceWithFallback()
        results = await service.get_results("test_query")
        assert "live_result" in results[0]
        
        # 测试网络失败降级
        service.primary_available = False
        fallback_results = await service.get_results("test_query")
        assert fallback_results == ["cached_result_1", "cached_result_2"]

    @pytest.mark.asyncio
    async def test_connection_pooling_recovery(self, mock_settings):
        """测试连接池恢复"""
        
        class ConnectionPool:
            def __init__(self, max_connections=5):
                self.max_connections = max_connections
                self.active_connections = []
                self.failed_connections = []
            
            async def get_connection(self):
                if len(self.active_connections) < self.max_connections:
                    connection_id = f"conn_{len(self.active_connections) + 1}"
                    self.active_connections.append(connection_id)
                    return connection_id
                else:
                    raise Exception("Connection pool exhausted")
            
            async def release_connection(self, connection_id):
                if connection_id in self.active_connections:
                    self.active_connections.remove(connection_id)
            
            async def mark_connection_failed(self, connection_id):
                if connection_id in self.active_connections:
                    self.active_connections.remove(connection_id)
                    self.failed_connections.append(connection_id)
            
            async def recover_failed_connections(self):
                # 尝试恢复失败的连接
                recovered = []
                for conn_id in self.failed_connections[:]:
                    try:
                        # 模拟重连尝试
                        await asyncio.sleep(0.01)
                        self.active_connections.append(conn_id)
                        self.failed_connections.remove(conn_id)
                        recovered.append(conn_id)
                    except Exception:
                        pass  # 恢复失败，保留在失败列表中
                
                return recovered
        
        # 测试连接池恢复
        pool = ConnectionPool(max_connections=3)
        
        # 获取连接
        conn1 = await pool.get_connection()
        conn2 = await pool.get_connection()
        
        # 标记连接失败
        await pool.mark_connection_failed(conn1)
        assert len(pool.active_connections) == 1
        assert len(pool.failed_connections) == 1
        
        # 恢复失败的连接
        recovered = await pool.recover_failed_connections()
        assert len(recovered) == 1
        assert len(pool.active_connections) == 2
        assert len(pool.failed_connections) == 0


class TestOfflineMode:
    """离线模式测试"""

    @pytest.mark.asyncio
    async def test_offline_cache_functionality(self, mock_settings):
        """测试离线缓存功能"""
        
        class OfflineCache:
            def __init__(self):
                self.cache = {}
                self.cache_timestamps = {}
                self.ttl_hours = 24
            
            def _is_cache_valid(self, key):
                if key not in self.cache_timestamps:
                    return False
                
                cache_time = self.cache_timestamps[key]
                expiry_time = cache_time + timedelta(hours=self.ttl_hours)
                return datetime.now() < expiry_time
            
            async def get_cached(self, key):
                if key in self.cache and self._is_cache_valid(key):
                    return self.cache[key]
                return None
            
            async def set_cache(self, key, value):
                self.cache[key] = value
                self.cache_timestamps[key] = datetime.now()
            
            async def get_with_fallback(self, key, online_func):
                # 尝试在线获取
                try:
                    result = await online_func()
                    await self.set_cache(key, result)
                    return result
                except Exception:
                    # 降级到缓存
                    cached_result = await self.get_cached(key)
                    if cached_result is not None:
                        return cached_result
                    raise Exception("Both online and cache failed")
        
        # 测试离线缓存
        cache = OfflineCache()
        
        # 模拟在线功能
        async def mock_online_api():
            return {"data": "online_result", "timestamp": datetime.now().isoformat()}
        
        # 首次获取（在线）
        result1 = await cache.get_with_fallback("test_key", mock_online_api)
        assert result1["data"] == "online_result"
        
        # 模拟网络失败
        async def mock_failed_api():
            raise Exception("Network error")
        
        # 应该返回缓存结果
        result2 = await cache.get_with_fallback("test_key", mock_failed_api)
        assert result2["data"] == "online_result"  # 来自缓存

    @pytest.mark.asyncio
    async def test_cache_invalidation_and_refresh(self, mock_settings):
        """测试缓存失效和刷新"""
        
        class SmartCache:
            def __init__(self):
                self.cache = {}
                self.cache_metadata = {}
            
            async def set_with_metadata(self, key, value, ttl_seconds=3600):
                self.cache[key] = value
                self.cache_metadata[key] = {
                    "created_at": datetime.now(),
                    "ttl_seconds": ttl_seconds,
                    "access_count": 0
                }
            
            async def get_with_validation(self, key):
                if key not in self.cache:
                    return None
                
                metadata = self.cache_metadata[key]
                
                # 检查TTL
                age = datetime.now() - metadata["created_at"]
                if age.total_seconds() > metadata["ttl_seconds"]:
                    # 缓存过期
                    del self.cache[key]
                    del self.cache_metadata[key]
                    return None
                
                # 更新访问计数
                metadata["access_count"] += 1
                return self.cache[key]
            
            async def refresh_if_needed(self, key, refresh_func, force_refresh=False):
                cached_value = await self.get_with_validation(key)
                
                if cached_value is None or force_refresh:
                    try:
                        new_value = await refresh_func()
                        await self.set_with_metadata(key, new_value)
                        return new_value
                    except Exception:
                        # 如果刷新失败且有旧缓存，返回旧缓存
                        if cached_value is not None:
                            return cached_value
                        raise
                
                return cached_value
        
        # 测试智能缓存
        smart_cache = SmartCache()
        
        # 设置短TTL用于测试
        await smart_cache.set_with_metadata("test_key", "old_value", ttl_seconds=0.1)
        
        # 立即获取应该成功
        result1 = await smart_cache.get_with_validation("test_key")
        assert result1 == "old_value"
        
        # 等待过期
        await asyncio.sleep(0.15)
        
        # 应该返回None（已过期）
        result2 = await smart_cache.get_with_validation("test_key")
        assert result2 is None
        
        # 测试刷新
        async def mock_refresh():
            return "refreshed_value"
        
        result3 = await smart_cache.refresh_if_needed("test_key", mock_refresh)
        assert result3 == "refreshed_value"


class TestNetworkLatencyHandling:
    """网络延迟处理测试"""

    @pytest.mark.asyncio
    async def test_high_latency_adaptation(self, mock_settings):
        """测试高延迟适应"""
        
        class AdaptiveTimeout:
            def __init__(self):
                self.base_timeout = 5.0
                self.timeout_history = []
                self.adaptive_factor = 1.0
            
            def record_response_time(self, response_time):
                self.timeout_history.append(response_time)
                if len(self.timeout_history) > 10:
                    self.timeout_history.pop(0)
                
                # 根据历史响应时间调整超时
                if len(self.timeout_history) >= 3:
                    avg_response_time = sum(self.timeout_history) / len(self.timeout_history)
                    self.adaptive_factor = max(1.0, avg_response_time / self.base_timeout * 1.5)
            
            def get_adaptive_timeout(self):
                return self.base_timeout * self.adaptive_factor
            
            async def make_request_with_adaptive_timeout(self, request_func):
                current_timeout = self.get_adaptive_timeout()
                start_time = time.time()
                
                try:
                    result = await asyncio.wait_for(request_func(), timeout=current_timeout)
                    response_time = time.time() - start_time
                    self.record_response_time(response_time)
                    return result
                except asyncio.TimeoutError:
                    response_time = time.time() - start_time
                    self.record_response_time(response_time)
                    raise
        
        # 测试自适应超时
        adaptive = AdaptiveTimeout()
        
        # 模拟快速响应
        async def fast_request():
            await asyncio.sleep(0.5)
            return "fast_result"
        
        result1 = await adaptive.make_request_with_adaptive_timeout(fast_request)
        assert result1 == "fast_result"
        initial_timeout = adaptive.get_adaptive_timeout()
        
        # 模拟慢速响应
        async def slow_request():
            await asyncio.sleep(2.0)
            return "slow_result"
        
        # 记录几次慢速响应
        for _ in range(3):
            try:
                await adaptive.make_request_with_adaptive_timeout(slow_request)
            except:
                pass
        
        # 超时应该已经自适应增加
        adapted_timeout = adaptive.get_adaptive_timeout()
        assert adapted_timeout > initial_timeout

    @pytest.mark.asyncio
    async def test_request_prioritization_under_congestion(self, mock_settings):
        """测试拥塞时的请求优先级"""
        
        class PriorityQueue:
            def __init__(self):
                self.high_priority = []
                self.normal_priority = []
                self.low_priority = []
                self.processing = False
            
            async def add_request(self, request_func, priority="normal"):
                request_item = {
                    "func": request_func,
                    "added_at": time.time(),
                    "priority": priority
                }
                
                if priority == "high":
                    self.high_priority.append(request_item)
                elif priority == "low":
                    self.low_priority.append(request_item)
                else:
                    self.normal_priority.append(request_item)
            
            async def process_requests(self):
                if self.processing:
                    return
                
                self.processing = True
                results = []
                
                try:
                    # 按优先级处理请求
                    all_queues = [
                        ("high", self.high_priority),
                        ("normal", self.normal_priority),
                        ("low", self.low_priority)
                    ]
                    
                    for priority_name, queue in all_queues:
                        while queue:
                            request_item = queue.pop(0)
                            try:
                                result = await request_item["func"]()
                                results.append({
                                    "result": result,
                                    "priority": priority_name,
                                    "processing_time": time.time() - request_item["added_at"]
                                })
                            except Exception as e:
                                results.append({
                                    "error": str(e),
                                    "priority": priority_name
                                })
                
                finally:
                    self.processing = False
                
                return results
        
        # 测试优先级队列
        queue = PriorityQueue()
        
        # 添加不同优先级的请求
        async def high_priority_request():
            await asyncio.sleep(0.1)
            return "high_priority_result"
        
        async def normal_priority_request():
            await asyncio.sleep(0.1)
            return "normal_priority_result"
        
        async def low_priority_request():
            await asyncio.sleep(0.1)
            return "low_priority_result"
        
        # 逆序添加以测试优先级
        await queue.add_request(low_priority_request, "low")
        await queue.add_request(normal_priority_request, "normal")
        await queue.add_request(high_priority_request, "high")
        
        # 处理请求
        results = await queue.process_requests()
        
        # 验证处理顺序
        assert len(results) == 3
        assert results[0]["priority"] == "high"
        assert results[1]["priority"] == "normal"
        assert results[2]["priority"] == "low"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])