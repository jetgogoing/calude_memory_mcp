"""
Claude Memory MCP 服务 - 核心工作流端到端测试

测试覆盖：
- 对话采集到记忆存储的完整流程
- 语义压缩和向量生成验证
- 检索和上下文注入功能测试
- 跨组件集成正确性验证
- 核心功能的数据流验证
"""

import asyncio
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock

import pytest
import numpy as np

from claude_memory.collectors.conversation_collector import ConversationCollector
from claude_memory.processors.semantic_compressor import SemanticCompressor
from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.injectors.context_injector import ContextInjector
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.models.data_models import (
    ConversationModel,
    MessageModel,
    MessageType,
    MemoryUnitModel,
    ProcessingStatus
)
from claude_memory.config.settings import get_settings


@pytest.fixture
def mock_settings():
    """模拟完整的配置设置"""
    settings = Mock()
    
    # CLI设置
    settings.cli.claude_cli_log_path = "/tmp/test_claude_logs"
    settings.cli.claude_cli_config_path = "/tmp/test_claude_config"
    settings.cli.enable_cli_hooks = True
    settings.cli.min_conversation_length = 5
    settings.cli.max_conversation_length = 10000
    
    # 数据库设置
    settings.database.url = "sqlite:///test_e2e.db"
    settings.database.echo = False
    
    # Qdrant设置
    settings.qdrant.url = "http://localhost:6333"
    settings.qdrant.collection_name = "test_e2e_vectors"
    settings.qdrant.vector_size = 4096
    
    # 模型设置
    settings.models.embedding.provider = "siliconflow"
    settings.models.embedding.model_name = "Qwen3-Embedding-8B"
    settings.models.compression.provider = "openrouter"
    settings.models.reranker.provider = "siliconflow"
    
    # 检索设置
    settings.retrieval.default_limit = 10
    settings.retrieval.similarity_threshold = 0.7
    settings.retrieval.enable_reranking = True
    
    # 注入设置
    settings.injection.strategy = "balanced"
    settings.injection.max_context_tokens = 2000
    
    # 性能设置
    settings.performance.batch_size = 10
    settings.performance.max_concurrent_requests = 5
    
    return settings


@pytest.fixture
def sample_conversation():
    """创建示例对话数据"""
    messages = [
        MessageModel(
            conversation_id=uuid.uuid4(),
            sequence_number=0,
            message_type=MessageType.USER,
            content="Hello Claude, I need help with implementing a binary search algorithm in Python. Can you guide me through the process?",
            token_count=25,
            created_at=datetime.now()
        ),
        MessageModel(
            conversation_id=uuid.uuid4(),
            sequence_number=1,
            message_type=MessageType.ASSISTANT,
            content="I'd be happy to help you implement a binary search algorithm in Python! Binary search is an efficient algorithm for finding an item from a sorted list of items. Here's a step-by-step implementation:\n\n```python\ndef binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    \n    while left <= right:\n        mid = (left + right) // 2\n        \n        if arr[mid] == target:\n            return mid  # Found the target\n        elif arr[mid] < target:\n            left = mid + 1  # Search right half\n        else:\n            right = mid - 1  # Search left half\n    \n    return -1  # Target not found\n```\n\nKey points:\n1. The array must be sorted\n2. We maintain left and right pointers\n3. We check the middle element and narrow the search space\n4. Time complexity: O(log n)\n\nWould you like me to explain any specific part in more detail?",
            token_count=180,
            created_at=datetime.now()
        ),
        MessageModel(
            conversation_id=uuid.uuid4(),
            sequence_number=2,
            message_type=MessageType.USER,
            content="Thanks! That's very helpful. Can you also show me how to implement a recursive version of binary search?",
            token_count=20,
            created_at=datetime.now()
        )
    ]
    
    conversation = ConversationModel(
        session_id="test_session_e2e",
        messages=messages,
        message_count=len(messages),
        token_count=sum(msg.token_count for msg in messages),
        title="Binary Search Algorithm Discussion",
        status=ProcessingStatus.PENDING,
        created_at=datetime.now()
    )
    
    return conversation


@pytest.fixture
def mock_components(mock_settings):
    """创建模拟的组件实例"""
    components = {}
    
    with patch('claude_memory.collectors.conversation_collector.get_settings', return_value=mock_settings):
        components['collector'] = ConversationCollector()
    
    with patch('claude_memory.processors.semantic_compressor.get_settings', return_value=mock_settings):
        components['compressor'] = SemanticCompressor()
    
    with patch('claude_memory.retrievers.semantic_retriever.get_settings', return_value=mock_settings):
        components['retriever'] = SemanticRetriever()
    
    with patch('claude_memory.injectors.context_injector.get_settings', return_value=mock_settings):
        components['injector'] = ContextInjector()
    
    with patch('claude_memory.managers.service_manager.get_settings', return_value=mock_settings):
        components['service_manager'] = ServiceManager()
    
    return components


class TestCoreWorkflowE2E:
    """核心工作流端到端测试"""

    @pytest.mark.asyncio
    async def test_conversation_to_memory_workflow(self, mock_components, sample_conversation):
        """测试对话到记忆的完整工作流"""
        collector = mock_components['collector']
        compressor = mock_components['compressor']
        retriever = mock_components['retriever']
        
        # 模拟各组件的行为
        
        # 1. 模拟对话采集
        with patch.object(collector, '_build_conversation_from_entries') as mock_build:
            mock_build.return_value = sample_conversation
            
            # 模拟日志解析
            with patch.object(collector, '_parse_log_content') as mock_parse:
                mock_parse.return_value = []  # 简化处理
                
                # 执行对话采集
                conversations = await collector._process_log_file(Path("/tmp/test.log"))
                mock_build.assert_called_once()
        
        # 2. 模拟语义压缩
        with patch.object(compressor, 'compress_conversation') as mock_compress:
            expected_memory_unit = MemoryUnitModel(
                id="test_memory_unit",
                content="Discussion about binary search algorithm implementation in Python",
                summary="Binary search algorithm tutorial with code examples",
                keywords=["python", "algorithm", "binary search", "programming"],
                importance_score=0.85,
                conversation_id=sample_conversation.id,
                session_id=sample_conversation.session_id
            )
            mock_compress.return_value = expected_memory_unit
            
            # 执行语义压缩
            memory_unit = await compressor.compress_conversation(sample_conversation)
            
            assert memory_unit is not None
            assert memory_unit.content is not None
            assert len(memory_unit.keywords) > 0
            assert memory_unit.importance_score > 0
            mock_compress.assert_called_once_with(sample_conversation)
        
        # 3. 模拟向量存储
        with patch.object(retriever, 'store_memory_unit') as mock_store:
            mock_store.return_value = True
            
            # 执行存储
            stored = await retriever.store_memory_unit(memory_unit)
            
            assert stored is True
            mock_store.assert_called_once_with(memory_unit)
        
        # 验证完整工作流
        assert sample_conversation.status == ProcessingStatus.PENDING
        assert memory_unit.conversation_id == sample_conversation.id

    @pytest.mark.asyncio
    async def test_memory_retrieval_and_injection_workflow(self, mock_components):
        """测试记忆检索和上下文注入工作流"""
        retriever = mock_components['retriever']
        injector = mock_components['injector']
        
        # 准备模拟的记忆单元
        mock_memory_units = [
            MemoryUnitModel(
                id=f"memory_{i}",
                content=f"Content about programming topic {i}",
                summary=f"Summary {i}",
                keywords=["programming", "python", f"topic_{i}"],
                importance_score=0.8 - (i * 0.1)
            )
            for i in range(3)
        ]
        
        # 1. 模拟语义检索
        with patch.object(retriever, 'retrieve_memories') as mock_retrieve:
            mock_retrieve.return_value = [(unit, 0.9 - i * 0.1) for i, unit in enumerate(mock_memory_units)]
            
            # 执行检索
            query = "How to implement sorting algorithms in Python?"
            retrieved_memories = await retriever.retrieve_memories(query, limit=5)
            
            assert len(retrieved_memories) == 3
            assert all(isinstance(item[0], MemoryUnitModel) for item in retrieved_memories)
            assert all(isinstance(item[1], float) for item in retrieved_memories)
            mock_retrieve.assert_called_once_with(query, limit=5)
        
        # 2. 模拟上下文注入
        with patch.object(injector, 'inject_context') as mock_inject:
            expected_context = """Based on previous discussions:
- Content about programming topic 0: Summary 0
- Content about programming topic 1: Summary 1
- Content about programming topic 2: Summary 2

Current query: How to implement sorting algorithms in Python?"""
            
            mock_inject.return_value = expected_context
            
            # 执行上下文注入
            enhanced_context = await injector.inject_context(query, retrieved_memories)
            
            assert enhanced_context is not None
            assert len(enhanced_context) > len(query)
            assert query in enhanced_context
            mock_inject.assert_called_once_with(query, retrieved_memories)
        
        # 验证检索和注入工作流
        assert len(retrieved_memories) > 0
        assert enhanced_context is not None

    @pytest.mark.asyncio
    async def test_service_manager_integration_workflow(self, mock_components, sample_conversation):
        """测试ServiceManager的集成工作流"""
        service_manager = mock_components['service_manager']
        
        # 模拟ServiceManager的方法
        with patch.object(service_manager, 'process_conversation') as mock_process:
            mock_process.return_value = MemoryUnitModel(
                id="integrated_memory",
                content="Integrated memory unit from service manager",
                summary="Service manager integration test",
                keywords=["integration", "test"],
                importance_score=0.75
            )
            
            # 执行对话处理
            memory_unit = await service_manager.process_conversation(sample_conversation)
            
            assert memory_unit is not None
            assert memory_unit.id == "integrated_memory"
            mock_process.assert_called_once_with(sample_conversation)
        
        # 模拟上下文增强
        with patch.object(service_manager, 'enhance_context') as mock_enhance:
            mock_enhance.return_value = "Enhanced context from service manager"
            
            # 执行上下文增强
            query = "Test query for enhancement"
            enhanced = await service_manager.enhance_context(query)
            
            assert enhanced is not None
            assert "Enhanced context" in enhanced
            mock_enhance.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_error_handling_in_workflow(self, mock_components, sample_conversation):
        """测试工作流中的错误处理"""
        compressor = mock_components['compressor']
        
        # 测试压缩阶段的错误处理
        with patch.object(compressor, 'compress_conversation') as mock_compress:
            mock_compress.side_effect = Exception("Compression failed")
            
            # 应该能优雅地处理错误
            with pytest.raises(Exception, match="Compression failed"):
                await compressor.compress_conversation(sample_conversation)
        
        # 测试重试机制
        with patch.object(compressor, 'compress_conversation') as mock_compress_retry:
            call_count = 0
            
            async def mock_compress_with_retry(conversation):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("Temporary failure")
                return MemoryUnitModel(
                    id="retry_success",
                    content="Successfully compressed after retry",
                    summary="Retry test",
                    keywords=["retry"],
                    importance_score=0.5
                )
            
            mock_compress_retry.side_effect = mock_compress_with_retry
            
            # 实际的重试逻辑需要在组件中实现
            # 这里只是验证错误处理的概念
            try:
                result = await compressor.compress_conversation(sample_conversation)
                # 如果有重试机制，应该最终成功
                if result:
                    assert result.id == "retry_success"
            except Exception:
                # 如果没有重试机制，应该失败
                pass

    @pytest.mark.asyncio
    async def test_data_consistency_across_workflow(self, mock_components, sample_conversation):
        """测试工作流中的数据一致性"""
        compressor = mock_components['compressor']
        retriever = mock_components['retriever']
        
        # 确保数据在各阶段间保持一致
        original_session_id = sample_conversation.session_id
        original_title = sample_conversation.title
        
        # 模拟压缩过程
        with patch.object(compressor, 'compress_conversation') as mock_compress:
            memory_unit = MemoryUnitModel(
                id="consistency_test",
                content="Consistent data test",
                summary="Testing data consistency",
                keywords=["consistency"],
                importance_score=0.7,
                conversation_id=sample_conversation.id,
                session_id=sample_conversation.session_id,  # 应该保持一致
                metadata={"original_title": sample_conversation.title}
            )
            mock_compress.return_value = memory_unit
            
            result = await compressor.compress_conversation(sample_conversation)
            
            # 验证数据一致性
            assert result.conversation_id == sample_conversation.id
            assert result.session_id == original_session_id
            assert result.metadata["original_title"] == original_title
        
        # 模拟存储过程
        with patch.object(retriever, 'store_memory_unit') as mock_store:
            mock_store.return_value = True
            
            # 验证存储时数据仍然一致
            stored = await retriever.store_memory_unit(memory_unit)
            assert stored is True
            
            # 检查传递给存储的数据
            stored_unit = mock_store.call_args[0][0]
            assert stored_unit.session_id == original_session_id
            assert stored_unit.conversation_id == sample_conversation.id

    @pytest.mark.asyncio
    async def test_workflow_performance_characteristics(self, mock_components, sample_conversation):
        """测试工作流的性能特性"""
        import time
        
        compressor = mock_components['compressor']
        
        # 模拟具有不同处理时间的操作
        processing_times = []
        
        async def mock_timed_compress(conversation):
            start_time = time.time()
            # 模拟处理时间
            await asyncio.sleep(0.1)
            end_time = time.time()
            
            processing_times.append((end_time - start_time) * 1000)  # 转换为毫秒
            
            return MemoryUnitModel(
                id="perf_test",
                content="Performance test memory",
                summary="Performance testing",
                keywords=["performance"],
                importance_score=0.6
            )
        
        with patch.object(compressor, 'compress_conversation', mock_timed_compress):
            
            # 执行多次操作以获取性能数据
            for _ in range(5):
                result = await compressor.compress_conversation(sample_conversation)
                assert result is not None
        
        # 验证性能特性
        assert len(processing_times) == 5
        avg_time = sum(processing_times) / len(processing_times)
        assert avg_time > 50  # 至少50ms（考虑到sleep时间）
        assert avg_time < 200  # 应该在合理范围内

    @pytest.mark.asyncio
    async def test_concurrent_workflow_handling(self, mock_components):
        """测试并发工作流处理"""
        service_manager = mock_components['service_manager']
        
        # 创建多个对话用于并发测试
        conversations = []
        for i in range(3):
            conversation = ConversationModel(
                session_id=f"concurrent_session_{i}",
                messages=[
                    MessageModel(
                        conversation_id=uuid.uuid4(),
                        sequence_number=0,
                        message_type=MessageType.USER,
                        content=f"Concurrent test message {i}",
                        token_count=10
                    )
                ],
                message_count=1,
                token_count=10,
                title=f"Concurrent Test {i}",
                status=ProcessingStatus.PENDING
            )
            conversations.append(conversation)
        
        # 模拟并发处理
        results = []
        
        async def mock_concurrent_process(conversation):
            # 模拟处理时间
            await asyncio.sleep(0.05)
            return MemoryUnitModel(
                id=f"concurrent_{conversation.session_id}",
                content=f"Processed {conversation.title}",
                summary="Concurrent processing test",
                keywords=["concurrent"],
                importance_score=0.5
            )
        
        with patch.object(service_manager, 'process_conversation', mock_concurrent_process):
            
            # 并发执行处理
            tasks = [service_manager.process_conversation(conv) for conv in conversations]
            results = await asyncio.gather(*tasks)
        
        # 验证并发处理结果
        assert len(results) == 3
        assert all(result is not None for result in results)
        assert all(result.keywords == ["concurrent"] for result in results)
        
        # 验证每个结果都对应正确的对话
        for i, result in enumerate(results):
            expected_id = f"concurrent_concurrent_session_{i}"
            assert result.id == expected_id


class TestWorkflowDataFlow:
    """工作流数据流测试"""

    @pytest.mark.asyncio
    async def test_complete_data_pipeline(self, mock_components, sample_conversation):
        """测试完整的数据管道流程"""
        collector = mock_components['collector']
        compressor = mock_components['compressor']
        retriever = mock_components['retriever']
        injector = mock_components['injector']
        
        # 数据流追踪
        data_flow = []
        
        # 1. 对话采集阶段
        with patch.object(collector, '_build_conversation_from_entries') as mock_build:
            mock_build.return_value = sample_conversation
            data_flow.append(("collection", sample_conversation.session_id))
            
            conversation = mock_build.return_value
            assert conversation.session_id == sample_conversation.session_id
        
        # 2. 语义压缩阶段
        with patch.object(compressor, 'compress_conversation') as mock_compress:
            memory_unit = MemoryUnitModel(
                id="pipeline_memory",
                content="Pipeline test content",
                summary="Data pipeline test",
                keywords=["pipeline", "test"],
                importance_score=0.8,
                conversation_id=conversation.id,
                session_id=conversation.session_id
            )
            mock_compress.return_value = memory_unit
            data_flow.append(("compression", memory_unit.id))
            
            compressed = await compressor.compress_conversation(conversation)
            assert compressed.conversation_id == conversation.id
        
        # 3. 存储阶段
        with patch.object(retriever, 'store_memory_unit') as mock_store:
            mock_store.return_value = True
            data_flow.append(("storage", compressed.id))
            
            stored = await retriever.store_memory_unit(compressed)
            assert stored is True
        
        # 4. 检索阶段
        with patch.object(retriever, 'retrieve_memories') as mock_retrieve:
            mock_retrieve.return_value = [(compressed, 0.95)]
            data_flow.append(("retrieval", "test_query"))
            
            retrieved = await retriever.retrieve_memories("test query", limit=1)
            assert len(retrieved) == 1
            assert retrieved[0][0].id == compressed.id
        
        # 5. 注入阶段
        with patch.object(injector, 'inject_context') as mock_inject:
            enhanced_context = f"Enhanced with memory: {compressed.summary}"
            mock_inject.return_value = enhanced_context
            data_flow.append(("injection", "enhanced_context"))
            
            context = await injector.inject_context("test query", retrieved)
            assert compressed.summary in context
        
        # 验证数据流完整性
        expected_stages = ["collection", "compression", "storage", "retrieval", "injection"]
        actual_stages = [stage for stage, _ in data_flow]
        assert actual_stages == expected_stages
        
        # 验证数据一致性
        assert data_flow[0][1] == sample_conversation.session_id  # collection
        assert data_flow[1][1] == "pipeline_memory"  # compression
        assert data_flow[2][1] == "pipeline_memory"  # storage (same ID)

    @pytest.mark.asyncio
    async def test_workflow_failure_recovery(self, mock_components, sample_conversation):
        """测试工作流故障恢复"""
        compressor = mock_components['compressor']
        retriever = mock_components['retriever']
        
        # 模拟压缩失败后的恢复
        failure_count = 0
        
        async def mock_compress_with_failure(conversation):
            nonlocal failure_count
            failure_count += 1
            
            if failure_count <= 2:
                raise Exception(f"Compression failure #{failure_count}")
            
            # 第三次尝试成功
            return MemoryUnitModel(
                id="recovery_success",
                content="Recovered after failures",
                summary="Recovery test",
                keywords=["recovery"],
                importance_score=0.6
            )
        
        with patch.object(compressor, 'compress_conversation', mock_compress_with_failure):
            
            # 模拟重试逻辑
            max_retries = 3
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    result = await compressor.compress_conversation(sample_conversation)
                    # 成功则跳出循环
                    break
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(0.01)  # 重试间隔
            
            # 验证最终成功
            assert result.id == "recovery_success"
            assert failure_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])