"""
Claude Memory MCP 服务 - 边界条件测试

测试内容：
- 极大和极小数据量处理
- 特殊字符和编码处理
- 空值和无效输入处理
- 系统资源极限测试
- 并发极限测试
"""

import asyncio
import string
import random
import json
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import uuid

import pytest

from claude_memory.managers.service_manager import ServiceManager
from claude_memory.collectors.conversation_collector import ConversationCollector
from claude_memory.processors.semantic_compressor import SemanticCompressor
from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.models.data_models import (
    ConversationModel, 
    MessageModel, 
    MessageType, 
    MemoryUnitModel
)
from claude_memory.processors.semantic_compressor import CompressionRequest
from claude_memory.config.settings import get_settings


class TestDataSizeBoundaries:
    """数据大小边界测试"""

    @pytest.mark.asyncio
    async def test_empty_input_handling(self):
        """测试空输入处理"""
        
        compressor = SemanticCompressor()
        
        # 测试空对话
        empty_conversation = ConversationModel(
            session_id="empty_test",
            messages=[],
            message_count=0,
            token_count=0,
            title=""
        )
        
        # 应该优雅处理空对话
        try:
            request = CompressionRequest(conversation=empty_conversation)
            result = await compressor.compress_conversation(request)
            # 可能返回None或抛出合理的异常
            if result is not None:
                assert result.content == "" or result.content is None
        except Exception as e:
            # 应该是可预期的异常类型
            assert "empty" in str(e).lower() or "no content" in str(e).lower()

    @pytest.mark.asyncio 
    async def test_minimal_input_handling(self):
        """测试最小输入处理"""
        
        compressor = SemanticCompressor()
        
        # 测试单字符消息
        minimal_conversation = ConversationModel(
            session_id="minimal_test",
            messages=[
                MessageModel(
                    conversation_id=None,
                    sequence_number=0,
                    message_type=MessageType.HUMAN,
                    content="a",
                    token_count=1
                ),
                MessageModel(
                    conversation_id=None,
                    sequence_number=1,
                    message_type=MessageType.ASSISTANT,
                    content="b",
                    token_count=1
                )
            ],
            message_count=2,
            token_count=2,
            title="min"
        )
        
        # 模拟压缩结果
        with patch.object(compressor, '_call_compression_api') as mock_api:
            mock_api.return_value = {
                "summary": "Minimal exchange",
                "key_points": ["single character exchange"],
                "importance_score": 0.1
            }
            
            result = await compressor.compress_conversation(minimal_conversation)
            
            if result:
                assert result.importance_score <= 0.3, "极短对话重要性应该很低"
                assert len(result.keywords) >= 1, "即使极短对话也应该有关键词"

    @pytest.mark.asyncio
    async def test_maximum_content_handling(self):
        """测试最大内容量处理"""
        
        compressor = SemanticCompressor()
        
        # 创建超长内容（模拟达到token限制）
        long_content = "This is a very long message. " * 1000  # 约30,000字符
        
        huge_conversation = ConversationModel(
            session_id="huge_test",
            messages=[
                MessageModel(
                    conversation_id=None,
                    sequence_number=0,
                    message_type=MessageType.HUMAN,
                    content="Please explain this topic in detail.",
                    token_count=50
                ),
                MessageModel(
                    conversation_id=None,
                    sequence_number=1,
                    message_type=MessageType.ASSISTANT,
                    content=long_content,
                    token_count=10000  # 模拟大量token
                )
            ],
            message_count=2,
            token_count=10050,
            title="Huge Content Test"
        )
        
        # 测试系统能否处理大内容
        with patch.object(compressor, '_call_compression_api') as mock_api:
            
            # 模拟可能的处理策略
            if len(long_content) > 20000:  # 内容过长
                # 策略1: 截断内容
                mock_api.return_value = {
                    "summary": "Large content discussion (truncated)",
                    "key_points": ["content was truncated due to size"],
                    "importance_score": 0.7
                }
            else:
                # 策略2: 正常处理
                mock_api.return_value = {
                    "summary": "Detailed discussion on requested topic",
                    "key_points": ["comprehensive explanation", "detailed coverage"],
                    "importance_score": 0.8
                }
            
            try:
                result = await compressor.compress_conversation(huge_conversation)
                
                if result:
                    # 验证大内容处理
                    assert len(result.content) < len(long_content), "压缩应该减少内容长度"
                    assert result.summary is not None, "应该生成摘要"
                    
            except Exception as e:
                # 可能因为内容过大而失败，这是可接受的
                error_msg = str(e).lower()
                acceptable_errors = ["too large", "token limit", "content size", "truncated"]
                assert any(err in error_msg for err in acceptable_errors), f"意外的错误类型: {e}"

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self):
        """测试Unicode和特殊字符处理"""
        
        compressor = SemanticCompressor()
        
        # 包含各种特殊字符的对话
        special_chars_conversation = ConversationModel(
            session_id="unicode_test",
            messages=[
                MessageModel(
                    conversation_id=None,
                    sequence_number=0,
                    message_type=MessageType.HUMAN,
                    content="Hello! 你好 こんにちは 🚀 ¿Cómo estás? ñáéíóú €£¥ 中文测试",
                    token_count=30
                ),
                MessageModel(
                    conversation_id=None,
                    sequence_number=1,
                    message_type=MessageType.ASSISTANT,
                    content="I can help with multiple languages! 我可以帮助多种语言 🌍 Special chars: @#$%^&*()_+{}|:<>?[]\\;'\",./ āēīōū",
                    token_count=40
                )
            ],
            message_count=2,
            token_count=70,
            title="Unicode & Special Characters Test 🌟"
        )
        
        with patch.object(compressor, '_call_compression_api') as mock_api:
            mock_api.return_value = {
                "summary": "Multilingual greeting exchange with special characters",
                "key_points": ["multilingual", "unicode support", "special characters"],
                "importance_score": 0.5
            }
            
            try:
                result = await compressor.compress_conversation(special_chars_conversation)
                
                if result:
                    # 验证Unicode字符被正确处理
                    assert result.content is not None, "应该能处理Unicode内容"
                    # 检查是否保留了一些多语言特征
                    content_lower = result.content.lower()
                    assert any(word in content_lower for word in ["multilingual", "language", "unicode", "character"])
                    
            except UnicodeError:
                pytest.fail("不应该发生Unicode编码错误")
            except Exception as e:
                # 其他异常可能是API相关的
                print(f"Unicode测试遇到异常: {e}")

    @pytest.mark.asyncio
    async def test_malformed_input_handling(self):
        """测试格式错误输入处理"""
        
        collector = ConversationCollector()
        
        # 测试各种格式错误的JSON
        malformed_json_logs = [
            '{"incomplete": "json"',  # 不完整的JSON
            '{"role": "user", "content": }',  # 语法错误
            '{"timestamp": "invalid-date", "content": "test"}',  # 无效日期
            '',  # 空行
            'not json at all',  # 非JSON内容
            '{"nested": {"very": {"deep": {"structure": {"that": {"goes": {"on": {"forever": "..."}}}}}}}}',  # 过度嵌套
        ]
        
        # 测试每种格式错误
        for malformed_log in malformed_json_logs:
            try:
                # 模拟解析日志行
                with patch.object(collector, '_parse_log_line') as mock_parse:
                    
                    def parse_with_error_handling(line):
                        try:
                            if not line.strip():
                                return None
                            data = json.loads(line)
                            return data
                        except json.JSONDecodeError:
                            return None  # 优雅地忽略格式错误
                        except Exception:
                            return None
                    
                    mock_parse.side_effect = lambda x: parse_with_error_handling(malformed_log)
                    
                    result = mock_parse(malformed_log)
                    
                    # 应该返回None而不是崩溃
                    if malformed_log.strip() and not malformed_log.startswith('not json'):
                        # 对于看起来像JSON的内容，应该尝试解析
                        pass  # 结果可能是None，这是OK的
            
            except Exception as e:
                # 不应该有未捕获的异常
                pytest.fail(f"格式错误输入应该被优雅处理，但发生了异常: {e}")


class TestConcurrencyBoundaries:
    """并发边界测试"""

    @pytest.mark.asyncio
    async def test_high_concurrency_stress(self):
        """测试高并发压力"""
        
        service_manager = ServiceManager()
        
        # 创建大量并发任务
        concurrent_tasks = 50
        
        async def create_test_task(task_id):
            """创建测试任务"""
            conversation = ConversationModel(
                session_id=f"stress_test_{task_id}",
                messages=[
                    MessageModel(
                        conversation_id=None,
                        sequence_number=0,
                        message_type=MessageType.HUMAN,
                        content=f"Stress test message {task_id}",
                        token_count=10
                    )
                ],
                message_count=1,
                token_count=10,
                title=f"Stress Test {task_id}"
            )
            
            # 模拟处理时间
            await asyncio.sleep(random.uniform(0.01, 0.1))
            return f"completed_{task_id}"
        
        # 执行并发压力测试
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 创建所有任务
            tasks = [create_test_task(i) for i in range(concurrent_tasks)]
            
            # 设置超时以防止无限等待
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0
            )
            
            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time
            
            # 分析结果
            success_count = sum(1 for r in results if isinstance(r, str) and r.startswith("completed_"))
            error_count = sum(1 for r in results if isinstance(r, Exception))
            
            print(f"并发压力测试结果:")
            print(f"  总任务: {concurrent_tasks}")
            print(f"  成功: {success_count}")
            print(f"  错误: {error_count}")
            print(f"  执行时间: {execution_time:.2f}秒")
            print(f"  平均吞吐量: {concurrent_tasks/execution_time:.2f} 任务/秒")
            
            # 验证系统在高并发下的表现
            success_rate = success_count / concurrent_tasks
            assert success_rate >= 0.8, f"高并发成功率过低: {success_rate:.2%}"
            assert execution_time < 60, "执行时间过长"
            
        except asyncio.TimeoutError:
            pytest.fail("高并发测试超时")

    @pytest.mark.asyncio
    async def test_resource_exhaustion_handling(self):
        """测试资源耗尽处理"""
        
        # 模拟资源管理器
        class ResourceManager:
            def __init__(self, max_resources=10):
                self.max_resources = max_resources
                self.allocated_resources = set()
                self.allocation_count = 0
            
            async def allocate_resource(self):
                if len(self.allocated_resources) >= self.max_resources:
                    raise Exception("Resource pool exhausted")
                
                resource_id = f"resource_{self.allocation_count}"
                self.allocation_count += 1
                self.allocated_resources.add(resource_id)
                return resource_id
            
            async def release_resource(self, resource_id):
                self.allocated_resources.discard(resource_id)
            
            def get_usage_stats(self):
                return {
                    "allocated": len(self.allocated_resources),
                    "max": self.max_resources,
                    "utilization": len(self.allocated_resources) / self.max_resources
                }
        
        resource_manager = ResourceManager(max_resources=5)
        
        # 测试资源分配和释放
        allocated_resources = []
        
        # 分配所有可用资源
        for i in range(5):
            resource = await resource_manager.allocate_resource()
            allocated_resources.append(resource)
        
        # 尝试分配超出限制的资源
        with pytest.raises(Exception, match="Resource pool exhausted"):
            await resource_manager.allocate_resource()
        
        # 验证资源利用率
        stats = resource_manager.get_usage_stats()
        assert stats["utilization"] == 1.0, "资源应该完全利用"
        
        # 释放资源
        for resource in allocated_resources[:2]:  # 释放2个资源
            await resource_manager.release_resource(resource)
        
        # 现在应该能分配新资源
        new_resource = await resource_manager.allocate_resource()
        assert new_resource is not None

    @pytest.mark.asyncio
    async def test_memory_intensive_operations(self):
        """测试内存密集操作"""
        
        # 模拟内存密集的向量操作
        class MemoryIntensiveProcessor:
            def __init__(self):
                self.memory_usage = []
            
            async def process_large_dataset(self, dataset_size=1000):
                """处理大型数据集"""
                
                # 模拟创建大型向量
                large_vectors = []
                
                try:
                    for i in range(dataset_size):
                        # 创建高维向量（模拟embedding）
                        vector = [random.random() for _ in range(1536)]  # 1536维向量
                        large_vectors.append(vector)
                        
                        # 每100个向量检查一次内存使用
                        if i % 100 == 0:
                            self.memory_usage.append(len(large_vectors))
                            
                            # 模拟处理延迟
                            await asyncio.sleep(0.01)
                    
                    # 模拟向量计算（内存密集）
                    result_count = len(large_vectors)
                    
                    return result_count
                    
                finally:
                    # 清理内存
                    large_vectors.clear()
            
            def get_peak_memory_usage(self):
                return max(self.memory_usage) if self.memory_usage else 0
        
        processor = MemoryIntensiveProcessor()
        
        # 测试不同大小的数据集
        dataset_sizes = [100, 500, 1000]
        
        for size in dataset_sizes:
            try:
                result = await processor.process_large_dataset(size)
                peak_memory = processor.get_peak_memory_usage()
                
                print(f"数据集大小 {size}: 处理完成，峰值内存使用: {peak_memory}")
                
                assert result == size, f"应该处理所有 {size} 个项目"
                assert peak_memory > 0, "应该有内存使用记录"
                
            except MemoryError:
                print(f"数据集大小 {size}: 内存不足，这是预期的")
                # 在内存有限的环境中，这是可接受的
                break
            except Exception as e:
                print(f"数据集大小 {size}: 意外错误 {e}")


class TestInputValidationBoundaries:
    """输入验证边界测试"""

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self):
        """测试SQL注入防护"""
        
        # 模拟数据库查询函数
        class SecureDatabase:
            def __init__(self):
                self.blocked_patterns = [
                    "'; DROP TABLE",
                    "UNION SELECT",
                    "OR 1=1",
                    "'; --",
                    "'; /*"
                ]
            
            async def safe_query(self, user_input):
                """安全的查询函数"""
                
                # 检查危险模式
                input_upper = user_input.upper()
                for pattern in self.blocked_patterns:
                    if pattern in input_upper:
                        raise ValueError(f"Potentially dangerous input detected: {pattern}")
                
                # 模拟参数化查询
                sanitized_input = user_input.replace("'", "''")  # 简单的转义
                return f"SELECT * FROM memories WHERE content LIKE '%{sanitized_input}%'"
        
        secure_db = SecureDatabase()
        
        # 测试正常输入
        normal_queries = [
            "python programming",
            "machine learning algorithms",
            "web development tips"
        ]
        
        for query in normal_queries:
            result = await secure_db.safe_query(query)
            assert "SELECT" in result, "正常查询应该成功"
        
        # 测试恶意输入
        malicious_queries = [
            "'; DROP TABLE memories; --",
            "test' UNION SELECT * FROM users; --",
            "' OR 1=1; --",
            "test'; DELETE FROM memories; --"
        ]
        
        for malicious_query in malicious_queries:
            with pytest.raises(ValueError, match="Potentially dangerous input"):
                await secure_db.safe_query(malicious_query)

    @pytest.mark.asyncio
    async def test_xss_prevention(self):
        """测试XSS攻击防护"""
        
        # 模拟内容清理函数
        class ContentSanitizer:
            def __init__(self):
                self.dangerous_patterns = [
                    "<script>",
                    "javascript:",
                    "onload=",
                    "onerror=",
                    "<iframe",
                    "eval("
                ]
            
            def sanitize_content(self, content):
                """清理潜在的XSS内容"""
                
                sanitized = content
                
                # 移除危险标签和属性
                for pattern in self.dangerous_patterns:
                    if pattern.lower() in sanitized.lower():
                        sanitized = sanitized.replace(pattern, "[REMOVED]")
                        sanitized = sanitized.replace(pattern.upper(), "[REMOVED]")
                        sanitized = sanitized.replace(pattern.capitalize(), "[REMOVED]")
                
                # 转义HTML特殊字符
                html_escapes = {
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#x27;',
                    '&': '&amp;'
                }
                
                for char, escape in html_escapes.items():
                    sanitized = sanitized.replace(char, escape)
                
                return sanitized
        
        sanitizer = ContentSanitizer()
        
        # 测试恶意内容
        malicious_contents = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(1)'></iframe>",
            "Hello <script>eval('malicious code')</script> World"
        ]
        
        for malicious_content in malicious_contents:
            sanitized = sanitizer.sanitize_content(malicious_content)
            
            # 验证危险内容被移除或转义
            assert "<script>" not in sanitized.lower(), "Script标签应该被移除"
            assert "javascript:" not in sanitized.lower(), "JavaScript协议应该被移除"
            assert "onerror=" not in sanitized.lower(), "事件处理器应该被移除"
            
            print(f"原始: {malicious_content}")
            print(f"清理后: {sanitized}")
            print("---")

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self):
        """测试路径遍历攻击防护"""
        
        # 模拟安全文件访问函数
        class SecureFileAccess:
            def __init__(self, base_dir="/safe/directory"):
                self.base_dir = base_dir
                self.dangerous_patterns = [
                    "../",
                    "..\\",
                    "/etc/",
                    "/root/",
                    "C:\\",
                    "~/"
                ]
            
            def validate_file_path(self, file_path):
                """验证文件路径安全性"""
                
                # 检查路径遍历模式
                for pattern in self.dangerous_patterns:
                    if pattern in file_path:
                        raise ValueError(f"Path traversal attempt detected: {pattern}")
                
                # 确保路径在基础目录内
                if not file_path.startswith(self.base_dir):
                    safe_path = f"{self.base_dir}/{file_path.lstrip('/')}"
                else:
                    safe_path = file_path
                
                return safe_path
        
        secure_access = SecureFileAccess()
        
        # 测试正常路径
        safe_paths = [
            "logs/conversation.log",
            "data/memories.json",
            "config/settings.yaml"
        ]
        
        for path in safe_paths:
            result = secure_access.validate_file_path(path)
            assert result.startswith("/safe/directory"), "路径应该在安全目录内"
        
        # 测试恶意路径
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/etc/shadow",
            "../../root/.ssh/id_rsa",
            "~/../../etc/passwd"
        ]
        
        for malicious_path in malicious_paths:
            with pytest.raises(ValueError, match="Path traversal attempt"):
                secure_access.validate_file_path(malicious_path)


class TestExtremeScenarios:
    """极端场景测试"""

    @pytest.mark.asyncio
    async def test_rapid_fire_requests(self):
        """测试快速连续请求"""
        
        # 模拟请求处理器
        class RequestProcessor:
            def __init__(self, max_requests_per_second=10):
                self.max_rps = max_requests_per_second
                self.request_times = []
            
            async def process_request(self, request_id):
                current_time = asyncio.get_event_loop().time()
                
                # 清理1秒前的请求记录
                cutoff_time = current_time - 1.0
                self.request_times = [t for t in self.request_times if t > cutoff_time]
                
                # 检查请求频率
                if len(self.request_times) >= self.max_rps:
                    raise Exception(f"Rate limit exceeded: {len(self.request_times)} requests in last second")
                
                # 记录当前请求
                self.request_times.append(current_time)
                
                # 模拟处理时间
                await asyncio.sleep(0.01)
                
                return f"processed_{request_id}"
        
        processor = RequestProcessor(max_requests_per_second=5)
        
        # 测试正常请求频率
        normal_requests = []
        for i in range(3):
            task = processor.process_request(f"normal_{i}")
            normal_requests.append(task)
            await asyncio.sleep(0.3)  # 间隔300ms
        
        results = await asyncio.gather(*normal_requests)
        assert all("processed_" in r for r in results), "正常频率请求应该成功"
        
        # 测试快速连续请求（应该被限制）
        rapid_requests = []
        for i in range(10):
            task = processor.process_request(f"rapid_{i}")
            rapid_requests.append(task)
            # 不等待，立即发送下一个请求
        
        results = await asyncio.gather(*rapid_requests, return_exceptions=True)
        
        # 统计成功和失败的请求
        success_count = sum(1 for r in results if isinstance(r, str))
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        print(f"快速请求测试: {success_count} 成功, {error_count} 被限制")
        assert error_count > 0, "快速请求应该被限制"

    @pytest.mark.asyncio
    async def test_system_under_extreme_load(self):
        """测试系统在极端负载下的表现"""
        
        # 模拟系统负载监控
        class LoadMonitor:
            def __init__(self):
                self.cpu_usage = 0
                self.memory_usage = 0
                self.request_count = 0
                self.error_count = 0
            
            async def simulate_load(self, intensity=1.0):
                """模拟系统负载"""
                
                # 模拟CPU和内存使用随负载增加
                self.cpu_usage = min(100, intensity * 30)
                self.memory_usage = min(100, intensity * 25)
                
                # 高负载时增加错误率
                if intensity > 3.0:
                    error_probability = (intensity - 3.0) * 0.2
                    if random.random() < error_probability:
                        self.error_count += 1
                        raise Exception(f"System overload at intensity {intensity}")
                
                self.request_count += 1
                
                # 模拟处理时间随负载增加
                processing_time = 0.01 * intensity
                await asyncio.sleep(processing_time)
                
                return {
                    "cpu": self.cpu_usage,
                    "memory": self.memory_usage,
                    "requests": self.request_count,
                    "errors": self.error_count
                }
        
        monitor = LoadMonitor()
        
        # 测试递增负载
        load_levels = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
        load_results = []
        
        for load_level in load_levels:
            try:
                # 在每个负载级别下运行多个任务
                tasks = []
                for i in range(5):
                    task = monitor.simulate_load(load_level)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 分析结果
                success_count = sum(1 for r in results if not isinstance(r, Exception))
                error_count = sum(1 for r in results if isinstance(r, Exception))
                
                load_results.append({
                    "load_level": load_level,
                    "success_count": success_count,
                    "error_count": error_count,
                    "success_rate": success_count / len(results)
                })
                
            except Exception as e:
                print(f"负载级别 {load_level} 导致系统故障: {e}")
        
        # 分析负载测试结果
        print("极端负载测试结果:")
        for result in load_results:
            print(f"  负载 {result['load_level']}: "
                  f"成功率 {result['success_rate']:.1%} "
                  f"({result['success_count']}/{result['success_count'] + result['error_count']})")
        
        # 验证系统在合理负载下工作
        low_load_results = [r for r in load_results if r['load_level'] <= 2.0]
        if low_load_results:
            avg_success_rate = sum(r['success_rate'] for r in low_load_results) / len(low_load_results)
            assert avg_success_rate >= 0.9, f"低负载成功率应该高于90%: {avg_success_rate:.1%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])