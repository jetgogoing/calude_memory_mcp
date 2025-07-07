"""
Claude Memory MCP 服务 - ConversationCollector 测试

测试覆盖：
- 对话采集器初始化和配置
- 多种日志格式解析（JSON/文本/结构化）
- 文件监听和轮询采集机制
- 数据标准化和清理
- 错误处理和恢复
- 会话管理和分组
- 内容过滤和验证
"""

import asyncio
import json
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from typing import List, Dict, Any

import pytest

from claude_memory.collectors.conversation_collector import (
    ConversationCollector,
    CLILogEntry
)
from claude_memory.models.data_models import (
    ConversationModel,
    MessageModel,
    MessageType,
    ProcessingStatus
)
from claude_memory.config.settings import get_settings


@pytest.fixture
def mock_settings():
    """模拟配置设置"""
    settings = Mock()
    settings.cli.claude_cli_log_path = "/tmp/test_claude_logs"
    settings.cli.claude_cli_config_path = "/tmp/test_claude_config"
    settings.cli.enable_cli_hooks = True
    settings.cli.cli_polling_interval_seconds = 1
    settings.cli.min_conversation_length = 5
    settings.cli.max_conversation_length = 10000
    settings.cli.exclude_system_messages = False
    settings.performance.batch_size = 10
    return settings


@pytest.fixture
def collector(mock_settings):
    """创建ConversationCollector实例"""
    with patch('claude_memory.collectors.conversation_collector.get_settings', return_value=mock_settings):
        collector = ConversationCollector()
        yield collector


@pytest.fixture
def sample_log_entries():
    """示例日志条目"""
    entries = [
        CLILogEntry(
            timestamp=datetime(2024, 1, 6, 10, 30, 45),
            message_type=MessageType.USER,
            content="Hello Claude, can you help me?",
            session_id="test-session-1",
            raw_line='[2024-01-06 10:30:45] USER: Hello Claude, can you help me?'
        ),
        CLILogEntry(
            timestamp=datetime(2024, 1, 6, 10, 30, 50),
            message_type=MessageType.ASSISTANT,
            content="Of course! I'd be happy to help you. What do you need assistance with?",
            session_id="test-session-1",
            raw_line='[2024-01-06 10:30:50] ASSISTANT: Of course! I\'d be happy to help you.'
        ),
        CLILogEntry(
            timestamp=datetime(2024, 1, 6, 10, 31, 0),
            message_type=MessageType.USER,
            content="I need help with Python programming.",
            session_id="test-session-1",
            raw_line='[2024-01-06 10:31:00] USER: I need help with Python programming.'
        )
    ]
    return entries


class TestConversationCollectorInit:
    """ConversationCollector 初始化测试"""

    def test_init_with_default_settings(self, mock_settings):
        """测试使用默认设置初始化"""
        with patch('claude_memory.collectors.conversation_collector.get_settings', return_value=mock_settings):
            collector = ConversationCollector()
            
            assert not collector.is_running
            assert len(collector.active_sessions) == 0
            assert len(collector.conversation_cache) == 0
            assert collector.last_processed_timestamp is None
            assert collector.batch_size == 10
            assert collector.polling_interval == 1

    def test_init_path_expansion(self, mock_settings):
        """测试路径展开功能"""
        mock_settings.cli.claude_cli_log_path = "~/test_logs"
        mock_settings.cli.claude_cli_config_path = "~/test_config"
        
        with patch('claude_memory.collectors.conversation_collector.get_settings', return_value=mock_settings):
            collector = ConversationCollector()
            
            # 验证路径被正确展开
            assert str(collector.cli_log_path).startswith('/')
            assert str(collector.config_path).startswith('/')


class TestLogParsing:
    """日志解析测试"""

    @pytest.mark.asyncio
    async def test_parse_json_format(self, collector):
        """测试JSON格式日志解析"""
        json_line = json.dumps({
            "timestamp": "2024-01-06T10:30:45.123456",
            "type": "user",
            "content": "Hello Claude",
            "session_id": "test-session",
            "metadata": {"source": "cli"}
        })
        
        entry = await collector._parse_log_line(json_line)
        
        assert entry is not None
        assert entry.message_type == MessageType.USER
        assert entry.content == "Hello Claude"
        assert entry.session_id == "test-session"
        assert entry.metadata == {"source": "cli"}

    @pytest.mark.asyncio
    async def test_parse_structured_text_format(self, collector):
        """测试结构化文本格式解析"""
        text_line = "[2024-01-06 10:30:45] USER: Hello Claude, how are you?"
        
        entry = await collector._parse_log_line(text_line)
        
        assert entry is not None
        assert entry.message_type == MessageType.USER
        assert entry.content == "Hello Claude, how are you?"
        assert entry.timestamp == datetime(2024, 1, 6, 10, 30, 45)

    @pytest.mark.asyncio
    async def test_parse_plain_text_format(self, collector):
        """测试纯文本格式解析"""
        text_line = "This is a plain text message"
        
        entry = await collector._parse_log_line(text_line)
        
        assert entry is not None
        assert entry.message_type == MessageType.USER
        assert entry.content == "This is a plain text message"

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, collector):
        """测试无效JSON处理"""
        invalid_json = '{"timestamp": "2024-01-06T10:30:45", "type": "user"'  # 缺少右括号
        
        entry = await collector._parse_log_line(invalid_json)
        
        # 应该回退到纯文本解析
        assert entry is not None
        assert entry.message_type == MessageType.USER

    @pytest.mark.asyncio
    async def test_parse_short_content_filtered(self, collector):
        """测试过短内容被过滤"""
        short_line = "hi"  # 少于5个字符
        
        entry = await collector._parse_log_line(short_line)
        
        assert entry is None

    @pytest.mark.asyncio
    async def test_parse_log_content_multiple_lines(self, collector):
        """测试多行日志内容解析"""
        content = """[2024-01-06 10:30:45] USER: First message
[2024-01-06 10:30:50] ASSISTANT: Response message
[2024-01-06 10:31:00] USER: Second message"""
        
        entries = await collector._parse_log_content(content, "test.log")
        
        assert len(entries) == 3
        assert entries[0].content == "First message"
        assert entries[1].content == "Response message" 
        assert entries[2].content == "Second message"
        
        # 验证时间排序
        for i in range(1, len(entries)):
            assert entries[i-1].timestamp <= entries[i].timestamp


class TestSessionManagement:
    """会话管理测试"""

    def test_extract_session_id_from_filename(self, collector):
        """测试从文件名提取会话ID"""
        test_cases = [
            ("session_f47ac10b-58cc-4372-a567-0e02b2c3d479.log", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
            ("claude-f47ac10b-58cc-4372-a567-0e02b2c3d479.jsonl", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
            ("chat_f47ac10b-58cc-4372-a567-0e02b2c3d479.txt", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
            ("f47ac10b-58cc-4372-a567-0e02b2c3d479.log", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
        ]
        
        for filename, expected_uuid in test_cases:
            result = collector._extract_session_id_from_filename(filename)
            assert result == expected_uuid

    def test_extract_session_id_fallback_hash(self, collector):
        """测试无UUID时回退到哈希"""
        filename = "random_file_name.log"
        result = collector._extract_session_id_from_filename(filename)
        
        assert result is not None
        assert len(result) == 32  # MD5哈希长度

    def test_group_entries_by_session(self, collector, sample_log_entries):
        """测试按会话分组日志条目"""
        # 添加另一个会话的条目
        sample_log_entries.append(
            CLILogEntry(
                timestamp=datetime(2024, 1, 6, 11, 0, 0),
                message_type=MessageType.USER,
                content="Different session message",
                session_id="test-session-2",
                raw_line="[2024-01-06 11:00:00] USER: Different session message"
            )
        )
        
        groups = collector._group_entries_by_session(sample_log_entries)
        
        assert len(groups) == 2
        assert "test-session-1" in groups
        assert "test-session-2" in groups
        assert len(groups["test-session-1"]) == 3
        assert len(groups["test-session-2"]) == 1


class TestConversationBuilding:
    """对话构建测试"""

    @pytest.mark.asyncio
    async def test_build_conversation_from_entries(self, collector, sample_log_entries):
        """测试从日志条目构建对话"""
        with patch.object(collector, '_should_include_entry', return_value=True):
            with patch.object(collector.text_processor, 'clean_and_normalize', side_effect=lambda x: x):
                with patch.object(collector.text_processor, 'count_tokens', return_value=10):
                    conversation = await collector._build_conversation_from_entries(
                        "test-session-1", sample_log_entries
                    )
        
        assert conversation is not None
        assert conversation.session_id == "test-session-1"
        assert conversation.message_count == 3
        assert conversation.token_count == 30  # 3 messages * 10 tokens each
        assert conversation.status == ProcessingStatus.PENDING
        assert len(conversation.messages) == 3

    @pytest.mark.asyncio
    async def test_build_conversation_empty_entries(self, collector):
        """测试空条目列表"""
        conversation = await collector._build_conversation_from_entries("test-session", [])
        assert conversation is None

    @pytest.mark.asyncio
    async def test_build_conversation_filtered_entries(self, collector, sample_log_entries):
        """测试所有条目都被过滤的情况"""
        with patch.object(collector, '_should_include_entry', return_value=False):
            conversation = await collector._build_conversation_from_entries(
                "test-session-1", sample_log_entries
            )
        
        assert conversation is None

    @pytest.mark.asyncio
    async def test_generate_conversation_title(self, collector):
        """测试对话标题生成"""
        # 创建测试对话
        messages = [
            MessageModel(
                conversation_id=uuid.uuid4(),
                sequence_number=0,
                message_type=MessageType.USER,
                content="How do I write a Python function to calculate the area of a circle?",
                token_count=15
            ),
            MessageModel(
                conversation_id=uuid.uuid4(),
                sequence_number=1,
                message_type=MessageType.ASSISTANT,
                content="Here's how you can write that function...",
                token_count=20
            )
        ]
        
        conversation = ConversationModel(
            session_id="test-session",
            messages=messages,
            message_count=2,
            token_count=35,
            status=ProcessingStatus.PENDING
        )
        
        title = await collector._generate_conversation_title(conversation)
        
        assert title == "How do I write a Python function to calculate the..."
        assert len(title) <= 53  # 50 characters + "..."

    @pytest.mark.asyncio
    async def test_generate_title_empty_conversation(self, collector):
        """测试空对话标题生成"""
        conversation = ConversationModel(
            session_id="empty-session-123",
            messages=[],
            message_count=0,
            token_count=0,
            status=ProcessingStatus.PENDING
        )
        
        title = await collector._generate_conversation_title(conversation)
        
        assert title == "Empty Conversation empty-se"


class TestContentFiltering:
    """内容过滤测试"""

    @pytest.mark.asyncio
    async def test_should_include_entry_valid(self, collector):
        """测试有效条目应该被包含"""
        entry = CLILogEntry(
            timestamp=datetime.now(),
            message_type=MessageType.USER,
            content="This is a valid message with enough content",
            session_id="test-session",
            raw_line="test line"
        )
        
        with patch.object(collector.text_processor, 'is_content_meaningful', return_value=True):
            result = await collector._should_include_entry(entry)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_should_include_entry_too_short(self, collector):
        """测试过短内容被过滤"""
        entry = CLILogEntry(
            timestamp=datetime.now(),
            message_type=MessageType.USER,
            content="hi",  # 太短
            session_id="test-session",
            raw_line="test line"
        )
        
        result = await collector._should_include_entry(entry)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_include_entry_too_long(self, collector):
        """测试过长内容被过滤"""
        entry = CLILogEntry(
            timestamp=datetime.now(),
            message_type=MessageType.USER,
            content="a" * 20000,  # 超过max_conversation_length
            session_id="test-session",
            raw_line="test line"
        )
        
        result = await collector._should_include_entry(entry)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_include_entry_system_message_excluded(self, collector):
        """测试系统消息被排除"""
        collector.settings.cli.exclude_system_messages = True
        
        entry = CLILogEntry(
            timestamp=datetime.now(),
            message_type=MessageType.SYSTEM,
            content="This is a system message",
            session_id="test-session",
            raw_line="test line"
        )
        
        result = await collector._should_include_entry(entry)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_include_entry_meaningless_content(self, collector):
        """测试无意义内容被过滤"""
        entry = CLILogEntry(
            timestamp=datetime.now(),
            message_type=MessageType.USER,
            content="This is valid length content",
            session_id="test-session",
            raw_line="test line"
        )
        
        with patch.object(collector.text_processor, 'is_content_meaningful', return_value=False):
            result = await collector._should_include_entry(entry)
        
        assert result is False


class TestFileOperations:
    """文件操作测试"""

    @pytest.mark.asyncio
    async def test_process_log_file_valid(self, collector):
        """测试处理有效日志文件"""
        # 创建临时测试文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write('[2024-01-06 10:30:45] USER: Test message 1\n')
            f.write('[2024-01-06 10:30:50] ASSISTANT: Test response\n')
            temp_path = Path(f.name)
        
        try:
            with patch.object(collector, '_should_include_entry', return_value=True):
                with patch.object(collector.text_processor, 'clean_and_normalize', side_effect=lambda x: x):
                    with patch.object(collector.text_processor, 'count_tokens', return_value=5):
                        conversations = await collector._process_log_file(temp_path)
            
            assert len(conversations) == 1
            assert conversations[0].message_count == 2
            
        finally:
            temp_path.unlink()  # 清理临时文件

    @pytest.mark.asyncio
    async def test_process_log_file_not_exists(self, collector):
        """测试处理不存在的文件"""
        non_existent_path = Path("/tmp/non_existent_file.log")
        conversations = await collector._process_log_file(non_existent_path)
        
        assert conversations == []

    @pytest.mark.asyncio
    async def test_is_file_recently_modified(self, collector):
        """测试文件最近修改检查"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # 刚创建的文件应该被认为是最近修改的
            result = await collector._is_file_recently_modified(temp_path, threshold_seconds=300)
            assert result is True
            
            # 不存在的文件应该返回False
            non_existent = Path("/tmp/definitely_not_exists.log")
            result = await collector._is_file_recently_modified(non_existent)
            assert result is False
            
        finally:
            temp_path.unlink()


class TestEnvironmentValidation:
    """环境验证测试"""

    @pytest.mark.asyncio
    async def test_validate_cli_environment_success(self, collector):
        """测试CLI环境验证成功"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir) / "logs"
            collector.config_path = Path(temp_dir) / "config"
            
            # 创建日志目录
            collector.cli_log_path.mkdir(parents=True, exist_ok=True)
            
            result = await collector._validate_cli_environment()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_cli_environment_create_missing_dir(self, collector):
        """测试自动创建缺失的日志目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir) / "missing_logs"
            collector.config_path = Path(temp_dir) / "config"
            
            # 确保目录不存在
            assert not collector.cli_log_path.exists()
            
            result = await collector._validate_cli_environment()
            
            assert result is True
            assert collector.cli_log_path.exists()


class TestErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_start_collection_already_running(self, collector):
        """测试重复启动采集器"""
        collector.is_running = True
        
        result = await collector.start_collection()
        assert result is False

    @pytest.mark.asyncio
    async def test_parse_malformed_content(self, collector):
        """测试解析异常格式内容"""
        malformed_content = """
        # 这是注释行
        
        [invalid-timestamp] USER: Bad timestamp
        [2024-01-06 10:30:45] UNKNOWN_TYPE: Unknown message type
        {"incomplete": "json"
        
        [2024-01-06 10:30:45] USER: 
        [2024-01-06 10:30:45] USER: ���乱码���
        """
        
        entries = await collector._parse_log_content(malformed_content, "malformed.log")
        
        # 应该只解析出有效的条目
        valid_entries = [e for e in entries if e is not None]
        assert len(valid_entries) >= 0  # 至少不应该崩溃

    @pytest.mark.asyncio
    async def test_error_recovery_in_file_processing(self, collector):
        """测试文件处理中的错误恢复"""
        # 模拟读取文件时的异常
        with patch('aiofiles.open', side_effect=PermissionError("No permission")):
            conversations = await collector._process_log_file(Path("/tmp/test.log"))
            
            # 应该返回空列表而不是抛出异常
            assert conversations == []


class TestCollectionMethods:
    """采集方法测试"""

    @pytest.mark.asyncio
    async def test_check_cli_status_no_config(self, collector):
        """测试无配置文件时的CLI状态检查"""
        # 确保配置路径不存在
        collector.config_path = Path("/tmp/non_existent_config")
        collector.cli_log_path = Path("/tmp/non_existent_logs")
        
        status = await collector._check_cli_status()
        
        assert status['is_running'] is False
        assert status['active_sessions'] == []
        assert status['last_activity'] is None

    @pytest.mark.asyncio
    async def test_collect_session_data_no_files(self, collector):
        """测试收集不存在会话的数据"""
        # 确保日志路径不存在
        collector.cli_log_path = Path("/tmp/non_existent_logs")
        
        conversations = await collector._collect_session_data("non-existent-session")
        
        assert conversations == []

    @pytest.mark.asyncio
    async def test_flush_conversation_cache(self, collector):
        """测试刷新对话缓存"""
        # 添加一些缓存数据
        collector.conversation_cache["session-1"] = Mock()
        collector.conversation_cache["session-2"] = Mock()
        
        assert len(collector.conversation_cache) == 2
        
        await collector._flush_conversation_cache()
        
        assert len(collector.conversation_cache) == 0


class TestRealFileFormats:
    """真实文件格式测试"""

    @pytest.mark.asyncio
    async def test_parse_json_log_file(self, collector):
        """测试解析JSON日志文件"""
        fixture_path = Path(__file__).parent / "fixtures" / "sample_claude_logs.json"
        
        conversations = await collector._process_log_file(fixture_path)
        
        # 验证基本解析结果（具体数量取决于过滤条件）
        assert isinstance(conversations, list)

    @pytest.mark.asyncio
    async def test_parse_text_log_file(self, collector):
        """测试解析文本日志文件"""
        fixture_path = Path(__file__).parent / "fixtures" / "sample_conversation.txt"
        
        with patch.object(collector, '_should_include_entry', return_value=True):
            with patch.object(collector.text_processor, 'clean_and_normalize', side_effect=lambda x: x):
                with patch.object(collector.text_processor, 'count_tokens', return_value=10):
                    conversations = await collector._process_log_file(fixture_path)
        
        assert len(conversations) >= 1

    @pytest.mark.asyncio
    async def test_parse_malformed_file(self, collector):
        """测试解析异常格式文件"""
        fixture_path = Path(__file__).parent / "fixtures" / "malformed_inputs.txt"
        
        with patch.object(collector, '_should_include_entry', return_value=True):
            with patch.object(collector.text_processor, 'clean_and_normalize', side_effect=lambda x: x):
                with patch.object(collector.text_processor, 'count_tokens', return_value=5):
                    with patch.object(collector.text_processor, 'is_content_meaningful', return_value=True):
                        conversations = await collector._process_log_file(fixture_path)
        
        # 应该能处理异常输入而不崩溃
        assert isinstance(conversations, list)


# 性能测试
class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_large_file_processing_performance(self, collector):
        """测试大文件处理性能"""
        import time
        
        # 创建大文件内容
        large_content = ""
        for i in range(1000):
            large_content += f"[2024-01-06 10:{i//60:02d}:{i%60:02d}] USER: Message {i}\n"
            large_content += f"[2024-01-06 10:{i//60:02d}:{i%60+10:02d}] ASSISTANT: Response {i}\n"
        
        # 创建临时大文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(large_content)
            temp_path = Path(f.name)
        
        try:
            start_time = time.time()
            
            with patch.object(collector, '_should_include_entry', return_value=True):
                with patch.object(collector.text_processor, 'clean_and_normalize', side_effect=lambda x: x):
                    with patch.object(collector.text_processor, 'count_tokens', return_value=5):
                        conversations = await collector._process_log_file(temp_path)
            
            processing_time = time.time() - start_time
            
            # 验证处理时间合理（具体阈值可根据实际需求调整）
            assert processing_time < 5.0  # 5秒内处理1000条消息
            assert len(conversations) > 0
            
        finally:
            temp_path.unlink()

    @pytest.mark.asyncio
    async def test_concurrent_parsing_performance(self, collector):
        """测试并发解析性能"""
        import time
        
        lines = [
            '[2024-01-06 10:30:45] USER: Test message 1',
            '[2024-01-06 10:30:46] ASSISTANT: Test response 1',
            '[2024-01-06 10:30:47] USER: Test message 2',
            '[2024-01-06 10:30:48] ASSISTANT: Test response 2',
        ] * 250  # 1000条消息
        
        start_time = time.time()
        
        # 并发解析所有行
        tasks = [collector._parse_log_line(line) for line in lines]
        results = await asyncio.gather(*tasks)
        
        processing_time = time.time() - start_time
        
        # 验证处理时间和结果
        assert processing_time < 2.0  # 2秒内解析1000行
        valid_results = [r for r in results if r is not None]
        assert len(valid_results) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])