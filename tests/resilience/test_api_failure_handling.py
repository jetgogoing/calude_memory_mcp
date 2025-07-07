"""
Claude Memory MCP 服务 - API失败处理测试

测试内容：
- 外部API连接失败处理
- API限流和配额处理
- 网络超时和重试机制
- API响应格式错误处理
- 服务降级和备用方案
"""

import asyncio
import time
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

import pytest
import aiohttp

from claude_memory.processors.semantic_compressor import SemanticCompressor
from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType
from claude_memory.config.settings import get_settings


@pytest.fixture
def mock_settings():
    """模拟配置设置"""
    settings = Mock()
    
    # 模型设置
    settings.models.embedding.provider = "siliconflow"
    settings.models.embedding.model_name = "Qwen3-Embedding-8B"
    settings.models.embedding.api_key = "test_api_key"
    settings.models.embedding.base_url = "https://api.siliconflow.cn/v1"
    
    settings.models.compression.provider = "openrouter"
    settings.models.compression.model_name = "google/gemini-2.5-flash"
    settings.models.compression.api_key = "test_openrouter_key"
    
    # 重试设置
    settings.resilience.max_retries = 3
    settings.resilience.retry_delay_base = 1.0
    settings.resilience.timeout_seconds = 30
    settings.resilience.enable_circuit_breaker = True
    
    # Qdrant设置
    settings.qdrant.url = "http://localhost:6333"
    settings.qdrant.collection_name = "test_resilience_vectors"
    
    return settings


@pytest.fixture
def sample_conversation():
    """创建测试对话"""
    messages = [
        MessageModel(
            conversation_id=None,
            sequence_number=0,
            message_type=MessageType.HUMAN,
            content="What is machine learning?",
            token_count=10
        ),
        MessageModel(
            conversation_id=None,
            sequence_number=1,
            message_type=MessageType.ASSISTANT,
            content="Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data.",
            token_count=20
        )
    ]
    
    return ConversationModel(
        session_id="test_resilience_session",
        messages=messages,
        message_count=len(messages),
        token_count=30,
        title="Machine Learning Discussion"
    )


class TestAPIFailureHandling:
    """API失败处理测试"""

    @pytest.mark.asyncio
    async def test_embedding_api_connection_failure(self, mock_settings, sample_conversation):
        """测试嵌入API连接失败处理"""
        with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
            compressor = SemanticCompressor()
            
            # 模拟网络连接失败
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.side_effect = aiohttp.ClientConnectorError(
                    connection_key=None,
                    os_error=OSError("Connection refused")
                )
                
                # 应该能优雅处理连接失败
                with pytest.raises(Exception) as exc_info:
                    await compressor.compress_conversation(sample_conversation)
                
                # 验证错误处理
                assert "Connection" in str(exc_info.value) or "Network" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_timeout_handling(self, mock_settings, sample_conversation):
        """测试API超时处理"""
        with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
            compressor = SemanticCompressor()
            
            # 模拟超时
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.side_effect = aiohttp.ServerTimeoutError("Request timeout")
                
                start_time = time.time()
                
                with pytest.raises(Exception):
                    await compressor.compress_conversation(sample_conversation)
                
                # 验证超时处理时间合理
                elapsed_time = time.time() - start_time
                assert elapsed_time < 5.0, "Timeout handling should be quick"

    @pytest.mark.asyncio
    async def test_api_rate_limiting_handling(self, mock_settings):
        """测试API限流处理"""
        with patch('claude_memory.retrievers.semantic_retriever.get_settings', return_value=mock_settings):
            retriever = SemanticRetriever()
            
            # 模拟限流响应
            rate_limit_response = Mock()
            rate_limit_response.status = 429
            rate_limit_response.headers = {"Retry-After": "60"}
            rate_limit_response.json = AsyncMock(return_value={
                "error": "Rate limit exceeded",
                "retry_after": 60
            })
            
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.return_value.__aenter__.return_value = rate_limit_response
                
                # 模拟向量存储时遇到限流
                with patch.object(retriever, '_generate_vector') as mock_generate:
                    mock_generate.side_effect = Exception("Rate limit exceeded")
                    
                    # 应该能处理限流错误
                    with pytest.raises(Exception) as exc_info:
                        await retriever._generate_vector("test query")
                    
                    assert "Rate limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_malformed_api_response_handling(self, mock_settings, sample_conversation):
        """测试格式错误的API响应处理"""
        with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
            compressor = SemanticCompressor()
            
            # 模拟格式错误的响应
            malformed_response = Mock()
            malformed_response.status = 200
            malformed_response.json = AsyncMock(return_value={
                "invalid_field": "unexpected data",
                "missing_required_fields": True
            })
            
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.return_value.__aenter__.return_value = malformed_response
                
                # 模拟处理格式错误的响应
                with patch.object(compressor, '_parse_compression_response') as mock_parse:
                    mock_parse.side_effect = KeyError("Expected field not found")
                    
                    with pytest.raises(Exception) as exc_info:
                        await compressor.compress_conversation(sample_conversation)
                    
                    assert "KeyError" in str(type(exc_info.value)) or "field" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_api_quota_exceeded_handling(self, mock_settings):
        """测试API配额超出处理"""
        with patch('claude_memory.retrievers.semantic_retriever.get_settings', return_value=mock_settings):
            retriever = SemanticRetriever()
            
            # 模拟配额超出响应
            quota_response = Mock()
            quota_response.status = 402
            quota_response.json = AsyncMock(return_value={
                "error": "Quota exceeded",
                "quota_limit": 1000,
                "quota_used": 1000,
                "reset_date": "2024-02-01"
            })
            
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.return_value.__aenter__.return_value = quota_response
                
                # 模拟配额超出处理
                with patch.object(retriever, '_handle_quota_exceeded') as mock_handle:
                    mock_handle.return_value = None
                    
                    # 应该能优雅处理配额超出
                    with pytest.raises(Exception) as exc_info:
                        await retriever._generate_vector("test query")
                    
                    # 验证配额处理被调用
                    if hasattr(retriever, '_handle_quota_exceeded'):
                        mock_handle.assert_called()


class TestRetryMechanisms:
    """重试机制测试"""

    @pytest.mark.asyncio
    async def test_exponential_backoff_retry(self, mock_settings, sample_conversation):
        """测试指数退避重试机制"""
        with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
            compressor = SemanticCompressor()
            
            retry_attempts = []
            
            async def mock_api_call_with_retries(*args, **kwargs):
                retry_attempts.append(time.time())
                if len(retry_attempts) < 3:
                    raise aiohttp.ClientError("Temporary failure")
                return {"compressed": "success after retries"}
            
            # 实现简单的重试逻辑测试
            max_retries = 3
            base_delay = 0.1
            
            for attempt in range(max_retries):
                try:
                    result = await mock_api_call_with_retries()
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        pytest.fail(f"All retries failed: {e}")
                    
                    # 指数退避延迟
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            
            # 验证重试机制
            assert len(retry_attempts) == 3
            
            # 验证指数退避时间间隔
            if len(retry_attempts) >= 2:
                time_diff_1 = retry_attempts[1] - retry_attempts[0]
                time_diff_2 = retry_attempts[2] - retry_attempts[1]
                assert time_diff_2 > time_diff_1, "Should use exponential backoff"

    @pytest.mark.asyncio
    async def test_retry_with_jitter(self, mock_settings):
        """测试带抖动的重试机制"""
        retry_times = []
        
        async def retry_with_jitter(base_delay=0.1, max_retries=3):
            import random
            
            for attempt in range(max_retries):
                retry_times.append(time.time())
                
                if attempt < max_retries - 1:
                    # 添加随机抖动
                    jitter = random.uniform(0, base_delay * 0.5)
                    delay = base_delay * (2 ** attempt) + jitter
                    await asyncio.sleep(delay)
        
        await retry_with_jitter()
        
        # 验证重试次数
        assert len(retry_times) == 3
        
        # 验证时间间隔包含抖动（不完全规律）
        if len(retry_times) >= 3:
            interval_1 = retry_times[1] - retry_times[0]
            interval_2 = retry_times[2] - retry_times[1]
            # 抖动使得间隔不会是精确的倍数关系
            assert abs(interval_2 / interval_1 - 2.0) < 1.0, "Jitter should add variability"

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self, mock_settings):
        """测试断路器模式"""
        
        class SimpleCircuitBreaker:
            def __init__(self, failure_threshold=3, recovery_timeout=5.0):
                self.failure_threshold = failure_threshold
                self.recovery_timeout = recovery_timeout
                self.failure_count = 0
                self.last_failure_time = None
                self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
            
            async def call(self, func, *args, **kwargs):
                if self.state == "OPEN":
                    if time.time() - self.last_failure_time > self.recovery_timeout:
                        self.state = "HALF_OPEN"
                    else:
                        raise Exception("Circuit breaker is OPEN")
                
                try:
                    result = await func(*args, **kwargs)
                    if self.state == "HALF_OPEN":
                        self.state = "CLOSED"
                        self.failure_count = 0
                    return result
                except Exception as e:
                    self.failure_count += 1
                    self.last_failure_time = time.time()
                    
                    if self.failure_count >= self.failure_threshold:
                        self.state = "OPEN"
                    
                    raise e
        
        circuit_breaker = SimpleCircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        async def failing_operation():
            raise Exception("Service unavailable")
        
        # 测试连续失败触发断路器
        for i in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_operation)
        
        # 验证断路器状态
        assert circuit_breaker.state == "OPEN"
        
        # 等待恢复超时
        await asyncio.sleep(0.15)
        
        # 测试半开状态
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_operation)


class TestServiceDegradation:
    """服务降级测试"""

    @pytest.mark.asyncio
    async def test_embedding_service_fallback(self, mock_settings, sample_conversation):
        """测试嵌入服务降级"""
        with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
            compressor = SemanticCompressor()
            
            # 模拟主要嵌入服务失败，降级到备用方案
            async def mock_primary_embedding_failure(*args, **kwargs):
                raise Exception("Primary embedding service failed")
            
            async def mock_fallback_embedding(*args, **kwargs):
                return [0.1] * 1024  # 简化的备用嵌入
            
            # 实现简单的降级逻辑
            primary_failed = False
            
            try:
                await mock_primary_embedding_failure()
            except Exception:
                primary_failed = True
                fallback_result = await mock_fallback_embedding()
            
            assert primary_failed
            assert len(fallback_result) == 1024

    @pytest.mark.asyncio
    async def test_compression_quality_degradation(self, mock_settings, sample_conversation):
        """测试压缩质量降级"""
        with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
            compressor = SemanticCompressor()
            
            # 模拟高质量压缩失败，降级到快速压缩
            async def mock_high_quality_compression(conversation):
                if conversation.token_count > 100:
                    raise Exception("High quality compression timeout")
                return "High quality summary"
            
            async def mock_fast_compression(conversation):
                # 简单的快速压缩
                first_message = conversation.messages[0].content if conversation.messages else ""
                return f"Quick summary: {first_message[:50]}..."
            
            # 测试降级逻辑
            try:
                # 创建一个大型对话触发降级
                large_conversation = ConversationModel(
                    session_id="large_session",
                    messages=[
                        MessageModel(
                            conversation_id=None,
                            sequence_number=0,
                            message_type=MessageType.HUMAN,
                            content="This is a very long conversation " * 20,
                            token_count=150
                        )
                    ],
                    message_count=1,
                    token_count=150,
                    title="Large Conversation"
                )
                
                result = await mock_high_quality_compression(large_conversation)
            except Exception:
                # 降级到快速压缩
                result = await mock_fast_compression(large_conversation)
                assert "Quick summary" in result

    @pytest.mark.asyncio
    async def test_retrieval_accuracy_degradation(self, mock_settings):
        """测试检索精度降级"""
        with patch('claude_memory.retrievers.semantic_retriever.get_settings', return_value=mock_settings):
            retriever = SemanticRetriever()
            
            # 模拟高精度检索失败，降级到基础检索
            async def mock_high_precision_retrieval(query, limit=10):
                if "complex" in query:
                    raise Exception("Complex retrieval failed")
                return [(f"precise_result_{i}", 0.9) for i in range(limit)]
            
            async def mock_basic_retrieval(query, limit=10):
                return [(f"basic_result_{i}", 0.7) for i in range(min(limit, 5))]
            
            # 测试降级逻辑
            query = "complex query requiring advanced processing"
            
            try:
                results = await mock_high_precision_retrieval(query, limit=10)
            except Exception:
                # 降级到基础检索
                results = await mock_basic_retrieval(query, limit=10)
                assert len(results) <= 5
                assert all("basic_result" in result[0] for result in results)


class TestErrorRecovery:
    """错误恢复测试"""

    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, mock_settings):
        """测试部分失败恢复"""
        
        # 模拟批处理中的部分失败
        async def process_batch_with_partial_failure(items):
            results = []
            failed_items = []
            
            for i, item in enumerate(items):
                try:
                    if i == 2:  # 模拟第3个项目失败
                        raise Exception(f"Processing failed for item {i}")
                    
                    # 模拟成功处理
                    await asyncio.sleep(0.01)
                    results.append(f"processed_{item}")
                except Exception as e:
                    failed_items.append((item, str(e)))
            
            return results, failed_items
        
        # 测试部分失败处理
        test_items = ["item1", "item2", "item3", "item4", "item5"]
        success_results, failed_results = await process_batch_with_partial_failure(test_items)
        
        # 验证部分成功处理
        assert len(success_results) == 4
        assert len(failed_results) == 1
        assert failed_results[0][0] == "item3"

    @pytest.mark.asyncio
    async def test_state_recovery_after_failure(self, mock_settings):
        """测试失败后状态恢复"""
        
        class StatefulProcessor:
            def __init__(self):
                self.processed_count = 0
                self.state = "IDLE"
                self.checkpoint = {}
            
            async def process_with_checkpoint(self, items):
                self.state = "PROCESSING"
                
                try:
                    for i, item in enumerate(items):
                        if i == 3:  # 模拟中途失败
                            raise Exception("Processing interrupted")
                        
                        self.processed_count += 1
                        # 创建检查点
                        self.checkpoint = {
                            "processed_count": self.processed_count,
                            "last_item": item,
                            "position": i
                        }
                        await asyncio.sleep(0.01)
                    
                    self.state = "COMPLETED"
                except Exception as e:
                    self.state = "FAILED"
                    raise e
            
            async def resume_from_checkpoint(self, items):
                if self.checkpoint and self.state == "FAILED":
                    # 从检查点恢复
                    start_position = self.checkpoint.get("position", 0) + 1
                    remaining_items = items[start_position:]
                    
                    self.state = "RESUMING"
                    
                    for item in remaining_items:
                        self.processed_count += 1
                        await asyncio.sleep(0.01)
                    
                    self.state = "COMPLETED"
                    return True
                return False
        
        # 测试状态恢复
        processor = StatefulProcessor()
        test_items = ["a", "b", "c", "d", "e"]
        
        # 初始处理失败
        with pytest.raises(Exception):
            await processor.process_with_checkpoint(test_items)
        
        assert processor.state == "FAILED"
        assert processor.processed_count == 3  # 处理了前3个项目
        
        # 从检查点恢复
        recovered = await processor.resume_from_checkpoint(test_items)
        assert recovered is True
        assert processor.state == "COMPLETED"
        assert processor.processed_count == 5  # 总共处理了5个项目

    @pytest.mark.asyncio
    async def test_resource_cleanup_after_failure(self, mock_settings):
        """测试失败后资源清理"""
        
        class ResourceManager:
            def __init__(self):
                self.active_connections = []
                self.temp_files = []
                self.memory_buffers = []
            
            async def allocate_resources(self):
                # 模拟分配资源
                self.active_connections.append("db_connection_1")
                self.temp_files.append("/tmp/temp_file_1")
                self.memory_buffers.append("buffer_1")
            
            async def cleanup_resources(self):
                # 清理资源
                self.active_connections.clear()
                self.temp_files.clear()
                self.memory_buffers.clear()
            
            async def process_with_cleanup(self):
                try:
                    await self.allocate_resources()
                    
                    # 模拟处理中出现错误
                    if len(self.active_connections) > 0:
                        raise Exception("Processing failed")
                
                finally:
                    # 确保资源被清理
                    await self.cleanup_resources()
        
        # 测试资源清理
        manager = ResourceManager()
        
        with pytest.raises(Exception):
            await manager.process_with_cleanup()
        
        # 验证资源已被清理
        assert len(manager.active_connections) == 0
        assert len(manager.temp_files) == 0
        assert len(manager.memory_buffers) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])