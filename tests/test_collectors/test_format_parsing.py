"""
Claude Memory MCP 服务 - 日志格式解析测试

测试覆盖：
- JSON格式日志解析
- 结构化文本格式解析
- 纯文本格式处理
- 混合格式处理
- 异常格式恢复
- 编码和特殊字符处理
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from claude_memory.collectors.conversation_collector import (
    ConversationCollector,
    CLILogEntry
)
from claude_memory.models.data_models import MessageType


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


class TestJSONFormatParsing:
    """JSON格式解析测试"""

    @pytest.mark.asyncio
    async def test_parse_valid_json_complete(self, collector):
        """测试解析完整有效的JSON格式"""
        json_data = {
            "timestamp": "2024-01-06T10:30:45.123456",
            "type": "user",
            "content": "Hello Claude, can you help me with Python?",
            "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "metadata": {
                "source": "claude_cli",
                "version": "1.0",
                "client": "web"
            }
        }
        
        json_line = json.dumps(json_data)
        entry = await collector._parse_log_line(json_line)
        
        assert entry is not None
        assert entry.message_type == MessageType.USER
        assert entry.content == "Hello Claude, can you help me with Python?"
        assert entry.session_id == "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        assert entry.metadata == json_data["metadata"]
        assert entry.raw_line == json_line

    @pytest.mark.asyncio
    async def test_parse_json_minimal_fields(self, collector):
        """测试解析最小字段的JSON"""
        json_data = {
            "content": "Minimal JSON message"
        }
        
        json_line = json.dumps(json_data)
        entry = await collector._parse_log_line(json_line)
        
        assert entry is not None
        assert entry.content == "Minimal JSON message"
        assert entry.message_type == MessageType.USER  # 默认类型
        assert entry.session_id is None

    @pytest.mark.asyncio
    async def test_parse_json_all_message_types(self, collector):
        """测试解析所有消息类型"""
        message_types = ["user", "assistant", "system"]
        
        for msg_type in message_types:
            json_data = {
                "type": msg_type,
                "content": f"This is a {msg_type} message"
            }
            
            json_line = json.dumps(json_data)
            entry = await collector._parse_log_line(json_line)
            
            assert entry is not None
            assert entry.message_type == MessageType(msg_type)
            assert entry.content == f"This is a {msg_type} message"

    @pytest.mark.asyncio
    async def test_parse_json_with_iso_timestamp(self, collector):
        """测试解析带ISO时间戳的JSON"""
        json_data = {
            "timestamp": "2024-01-06T10:30:45.123456Z",
            "type": "assistant",
            "content": "Message with ISO timestamp"
        }
        
        json_line = json.dumps(json_data)
        entry = await collector._parse_log_line(json_line)
        
        assert entry is not None
        assert entry.timestamp.year == 2024
        assert entry.timestamp.month == 1
        assert entry.timestamp.day == 6

    @pytest.mark.asyncio
    async def test_parse_malformed_json_recovery(self, collector):
        """测试格式错误的JSON恢复到文本解析"""
        malformed_json_lines = [
            '{"timestamp": "2024-01-06T10:30:45", "type": "user"',  # 缺少右括号
            '{"timestamp": "2024-01-06T10:30:45", "type": "user", "content": }',  # 缺少值
            '{"timestamp": 2024-01-06T10:30:45, "type": "user", "content": "test"}',  # 无效时间戳
            '{timestamp: "2024-01-06T10:30:45", type: "user", content: "test"}',  # 无引号键
        ]
        
        for malformed_line in malformed_json_lines:
            entry = await collector._parse_log_line(malformed_line)
            
            # 应该回退到文本解析，如果内容足够长
            if len(malformed_line) >= collector.settings.cli.min_conversation_length:
                assert entry is not None
                assert entry.message_type == MessageType.USER
                assert entry.content == malformed_line.strip()

    @pytest.mark.asyncio
    async def test_parse_json_with_unicode_content(self, collector):
        """测试解析包含Unicode内容的JSON"""
        json_data = {
            "type": "user",
            "content": "Hello 世界! How are you today? 🎉",
            "metadata": {"emoji": "🚀", "chinese": "你好"}
        }
        
        json_line = json.dumps(json_data, ensure_ascii=False)
        entry = await collector._parse_log_line(json_line)
        
        assert entry is not None
        assert entry.content == "Hello 世界! How are you today? 🎉"
        assert entry.metadata["emoji"] == "🚀"
        assert entry.metadata["chinese"] == "你好"

    @pytest.mark.asyncio
    async def test_parse_json_with_nested_metadata(self, collector):
        """测试解析包含嵌套元数据的JSON"""
        json_data = {
            "type": "assistant",
            "content": "Complex metadata message",
            "metadata": {
                "performance": {
                    "response_time": 150,
                    "tokens_used": 45
                },
                "context": {
                    "previous_turns": 3,
                    "session_length": "5m"
                },
                "tags": ["helpful", "coding", "python"]
            }
        }
        
        json_line = json.dumps(json_data)
        entry = await collector._parse_log_line(json_line)
        
        assert entry is not None
        assert entry.metadata["performance"]["response_time"] == 150
        assert entry.metadata["context"]["previous_turns"] == 3
        assert "python" in entry.metadata["tags"]


class TestStructuredTextParsing:
    """结构化文本格式解析测试"""

    @pytest.mark.asyncio
    async def test_parse_standard_structured_format(self, collector):
        """测试标准结构化文本格式"""
        test_cases = [
            ("[2024-01-06 10:30:45] USER: Hello Claude", MessageType.USER, "Hello Claude"),
            ("[2024-01-06 10:30:50] ASSISTANT: Hello! How can I help?", MessageType.ASSISTANT, "Hello! How can I help?"),
            ("[2024-01-06 10:31:00] SYSTEM: Session started", MessageType.SYSTEM, "Session started"),
        ]
        
        for line, expected_type, expected_content in test_cases:
            entry = await collector._parse_log_line(line)
            
            assert entry is not None
            assert entry.message_type == expected_type
            assert entry.content == expected_content
            assert entry.timestamp == datetime(2024, 1, 6, 10, 30, 45) or \
                   entry.timestamp == datetime(2024, 1, 6, 10, 30, 50) or \
                   entry.timestamp == datetime(2024, 1, 6, 10, 31, 0)

    @pytest.mark.asyncio
    async def test_parse_structured_with_various_separators(self, collector):
        """测试不同分隔符的结构化格式"""
        test_cases = [
            "[2024-01-06 10:30:45] USER: Message with colon",
            "[2024-01-06 10:30:45]USER:No spaces around",
            "[2024-01-06 10:30:45]   USER   :   Extra spaces   ",
        ]
        
        for line in test_cases:
            entry = await collector._parse_log_line(line)
            
            assert entry is not None
            assert entry.message_type == MessageType.USER

    @pytest.mark.asyncio
    async def test_parse_structured_multiline_content(self, collector):
        """测试结构化格式的多行内容"""
        line = "[2024-01-06 10:30:45] USER: This is a message\\nwith multiple lines\\nand special chars: !@#$%"
        
        entry = await collector._parse_log_line(line)
        
        assert entry is not None
        assert entry.message_type == MessageType.USER
        assert "multiple lines" in entry.content
        assert "!@#$%" in entry.content

    @pytest.mark.asyncio
    async def test_parse_structured_invalid_timestamp(self, collector):
        """测试无效时间戳的结构化格式"""
        invalid_lines = [
            "[invalid-date] USER: Message with bad timestamp",
            "[2024-13-40 25:70:90] USER: Impossible date/time",
            "[2024/01/06 10:30:45] USER: Wrong date format",
        ]
        
        for line in invalid_lines:
            entry = await collector._parse_log_line(line)
            
            # 应该回退到纯文本解析
            if len(line) >= collector.settings.cli.min_conversation_length:
                assert entry is not None
                assert entry.message_type == MessageType.USER
                assert entry.content == line.strip()

    @pytest.mark.asyncio
    async def test_parse_structured_unknown_message_type(self, collector):
        """测试未知消息类型的处理"""
        line = "[2024-01-06 10:30:45] UNKNOWN_TYPE: Message with unknown type"
        
        entry = await collector._parse_log_line(line)
        
        # 应该回退到纯文本解析
        if len(line) >= collector.settings.cli.min_conversation_length:
            assert entry is not None
            assert entry.message_type == MessageType.USER
            assert entry.content == line.strip()

    @pytest.mark.asyncio
    async def test_parse_structured_empty_content(self, collector):
        """测试空内容的结构化格式"""
        line = "[2024-01-06 10:30:45] USER:"
        
        entry = await collector._parse_log_line(line)
        
        # 内容太短，应该返回None
        assert entry is None

    @pytest.mark.asyncio
    async def test_parse_structured_with_unicode(self, collector):
        """测试包含Unicode的结构化格式"""
        line = "[2024-01-06 10:30:45] USER: 你好Claude，今天天气怎么样？🌤️"
        
        entry = await collector._parse_log_line(line)
        
        assert entry is not None
        assert entry.message_type == MessageType.USER
        assert "你好Claude" in entry.content
        assert "🌤️" in entry.content


class TestPlainTextParsing:
    """纯文本格式解析测试"""

    @pytest.mark.asyncio
    async def test_parse_plain_text_valid_length(self, collector):
        """测试有效长度的纯文本"""
        plain_texts = [
            "This is a simple plain text message",
            "Another message without any special formatting",
            "可以处理中文纯文本消息",
            "Mixed content with 中文 and English and 123 numbers",
        ]
        
        for text in plain_texts:
            entry = await collector._parse_log_line(text)
            
            assert entry is not None
            assert entry.message_type == MessageType.USER
            assert entry.content == text.strip()

    @pytest.mark.asyncio
    async def test_parse_plain_text_too_short(self, collector):
        """测试过短的纯文本"""
        short_texts = [
            "hi",
            "ok",
            "yes",
            "no",
            "👍",
        ]
        
        for text in short_texts:
            entry = await collector._parse_log_line(text)
            
            # 应该返回None因为太短
            assert entry is None

    @pytest.mark.asyncio
    async def test_parse_plain_text_whitespace_handling(self, collector):
        """测试纯文本的空白字符处理"""
        test_cases = [
            ("   Leading and trailing spaces   ", "Leading and trailing spaces"),
            ("\t\tTabs at beginning\t\t", "Tabs at beginning"),
            ("Multiple\n\nline\n\nbreaks", "Multiple\n\nline\n\nbreaks"),
            ("   \n   Only whitespace   \n   ", "Only whitespace"),
        ]
        
        for input_text, expected_output in test_cases:
            if len(expected_output.strip()) >= collector.settings.cli.min_conversation_length:
                entry = await collector._parse_log_line(input_text)
                
                assert entry is not None
                assert entry.content == expected_output.strip()

    @pytest.mark.asyncio
    async def test_parse_plain_text_special_characters(self, collector):
        """测试包含特殊字符的纯文本"""
        special_texts = [
            "Text with special chars: !@#$%^&*()",
            "HTML-like content: <div>hello</div>",
            "Code snippet: def hello(): return 'world'",
            "URLs: https://example.com/path?param=value",
            "JSON-like but not valid: {key: value, other: data}",
        ]
        
        for text in special_texts:
            entry = await collector._parse_log_line(text)
            
            assert entry is not None
            assert entry.content == text.strip()
            assert entry.message_type == MessageType.USER


class TestMixedFormatHandling:
    """混合格式处理测试"""

    @pytest.mark.asyncio
    async def test_parse_log_content_mixed_formats(self, collector):
        """测试混合格式的日志内容"""
        mixed_content = '''{"timestamp": "2024-01-06T10:30:45", "type": "user", "content": "JSON format message"}
[2024-01-06 10:30:50] ASSISTANT: Structured text format response
Plain text message without any formatting
{"timestamp": "2024-01-06T10:31:00", "type": "user", "content": "Another JSON message"}
[2024-01-06 10:31:05] USER: Back to structured format'''
        
        entries = await collector._parse_log_content(mixed_content, "mixed.log")
        
        # 应该解析出5条消息
        assert len(entries) == 5
        
        # 验证第一条JSON格式
        assert entries[0].content == "JSON format message"
        assert entries[0].message_type == MessageType.USER
        
        # 验证第二条结构化文本格式
        assert entries[1].content == "Structured text format response"
        assert entries[1].message_type == MessageType.ASSISTANT
        
        # 验证第三条纯文本格式
        assert entries[2].content == "Plain text message without any formatting"
        assert entries[2].message_type == MessageType.USER

    @pytest.mark.asyncio
    async def test_parse_log_content_with_empty_lines(self, collector):
        """测试包含空行的日志内容"""
        content_with_empty_lines = '''[2024-01-06 10:30:45] USER: First message

[2024-01-06 10:30:50] ASSISTANT: Second message


[2024-01-06 10:31:00] USER: Third message

'''
        
        entries = await collector._parse_log_content(content_with_empty_lines, "empty_lines.log")
        
        # 空行应该被忽略
        assert len(entries) == 3
        assert entries[0].content == "First message"
        assert entries[1].content == "Second message"
        assert entries[2].content == "Third message"

    @pytest.mark.asyncio
    async def test_parse_log_content_chronological_sorting(self, collector):
        """测试时间顺序排序"""
        unordered_content = '''[2024-01-06 10:31:00] USER: Third message
{"timestamp": "2024-01-06T10:30:45", "type": "user", "content": "First message"}
[2024-01-06 10:30:50] ASSISTANT: Second message'''
        
        entries = await collector._parse_log_content(unordered_content, "unordered.log")
        
        # 应该按时间排序
        assert len(entries) == 3
        assert entries[0].content == "First message"
        assert entries[1].content == "Second message"
        assert entries[2].content == "Third message"
        
        # 验证时间排序
        for i in range(1, len(entries)):
            assert entries[i-1].timestamp <= entries[i].timestamp


class TestErrorRecoveryAndResilience:
    """错误恢复和韧性测试"""

    @pytest.mark.asyncio
    async def test_parse_corrupted_content(self, collector):
        """测试解析损坏的内容"""
        corrupted_lines = [
            "���乱码内容���",  # 二进制乱码
            "\x00\x01\x02invalid binary",  # 二进制字符
            "♠♣♥♦ Special Unicode symbols ♠♣♥♦",  # 特殊Unicode符号
            "Very long line " + "x" * 10000,  # 超长行
        ]
        
        for line in corrupted_lines:
            # 不应该抛出异常
            entry = await collector._parse_log_line(line)
            
            # 根据长度决定是否应该解析
            if len(line.strip()) >= collector.settings.cli.min_conversation_length:
                if len(line.strip()) <= collector.settings.cli.max_conversation_length:
                    assert entry is not None
                else:
                    assert entry is None  # 太长被过滤
            else:
                assert entry is None  # 太短被过滤

    @pytest.mark.asyncio
    async def test_parse_encoding_issues(self, collector):
        """测试编码问题处理"""
        # 模拟各种编码问题
        encoding_test_cases = [
            "Café with accents àáâãäå",
            "Russian text: Привет мир",
            "Chinese text: 你好世界",
            "Japanese text: こんにちは世界",
            "Arabic text: مرحبا بالعالم",
            "Mixed: Hello 世界 Привет 🌍",
        ]
        
        for text in encoding_test_cases:
            entry = await collector._parse_log_line(text)
            
            assert entry is not None
            assert entry.content == text.strip()

    @pytest.mark.asyncio
    async def test_parse_extremely_malformed_json(self, collector):
        """测试极端格式错误的JSON"""
        malformed_jsons = [
            '{"key":: "double colon"}',
            '{key without quotes: "value"}',
            '{"missing_quote: "value"}',
            '{"trailing_comma": "value",}',
            '{"unclosed_string": "value}',
            '{[array_as_key]: "value"}',
            '{"null_value": null undefined}',
        ]
        
        for malformed in malformed_jsons:
            # 不应该抛出异常
            entry = await collector._parse_log_line(malformed)
            
            # 应该回退到文本解析
            if len(malformed) >= collector.settings.cli.min_conversation_length:
                assert entry is not None
                assert entry.message_type == MessageType.USER

    @pytest.mark.asyncio
    async def test_parse_performance_with_large_content(self, collector):
        """测试大内容的解析性能"""
        import time
        
        # 创建大内容
        large_json = {
            "type": "user",
            "content": "Large content: " + "x" * 5000,
            "metadata": {"large_field": "y" * 1000}
        }
        large_json_line = json.dumps(large_json)
        
        start_time = time.time()
        entry = await collector._parse_log_line(large_json_line)
        parse_time = time.time() - start_time
        
        # 验证解析成功且在合理时间内完成
        assert entry is not None
        assert parse_time < 1.0  # 应该在1秒内完成
        assert len(entry.content) > 5000


class TestSessionIdExtraction:
    """会话ID提取测试"""

    def test_extract_session_id_various_patterns(self, collector):
        """测试各种文件名模式的会话ID提取"""
        test_cases = [
            # 标准UUID格式
            ("session_f47ac10b-58cc-4372-a567-0e02b2c3d479.log", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
            ("claude-f47ac10b-58cc-4372-a567-0e02b2c3d479.jsonl", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
            ("chat_f47ac10b-58cc-4372-a567-0e02b2c3d479.txt", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
            
            # UUID without prefix
            ("f47ac10b-58cc-4372-a567-0e02b2c3d479.log", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
            
            # 不同大小写
            ("SESSION_F47AC10B-58CC-4372-A567-0E02B2C3D479.LOG", "F47AC10B-58CC-4372-A567-0E02B2C3D479"),
            
            # 复杂文件名
            ("claude_session_backup_f47ac10b-58cc-4372-a567-0e02b2c3d479_2024.log", "f47ac10b-58cc-4372-a567-0e02b2c3d479"),
            
            # 无UUID的文件名
            ("random_file_name.log", None),  # 会回退到MD5哈希
            ("chat_log_2024_01_06.txt", None),  # 会回退到MD5哈希
        ]
        
        for filename, expected_uuid in test_cases:
            result = collector._extract_session_id_from_filename(filename)
            
            if expected_uuid:
                assert result == expected_uuid
            else:
                # 应该返回MD5哈希
                assert result is not None
                assert len(result) == 32  # MD5哈希长度

    def test_extract_session_id_edge_cases(self, collector):
        """测试边界情况的会话ID提取"""
        edge_cases = [
            "",  # 空文件名
            ".",  # 只有点
            ".log",  # 只有扩展名
            "f47ac10b.log",  # 不完整的UUID
            "not-a-uuid-format.log",  # 非UUID格式
            "multiple-f47ac10b-58cc-4372-a567-0e02b2c3d479-and-f47ac10b-58cc-4372-a567-0e02b2c3d480.log",  # 多个UUID
        ]
        
        for filename in edge_cases:
            result = collector._extract_session_id_from_filename(filename)
            
            # 所有情况都应该返回某种ID（UUID或MD5哈希）
            assert result is not None
            assert len(result) >= 32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])