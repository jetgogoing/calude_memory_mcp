"""
Claude Memory MCP 服务 - 文件监听采集器测试

测试覆盖：
- 文件监听机制
- 文件变化检测
- 实时日志处理
- 监听器生命周期管理
- 文件权限和错误处理
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

from claude_memory.collectors.conversation_collector import ConversationCollector
from claude_memory.models.data_models import MessageType


@pytest.fixture
def mock_settings():
    """模拟配置设置"""
    settings = Mock()
    settings.cli.claude_cli_log_path = "/tmp/test_claude_logs"
    settings.cli.claude_cli_config_path = "/tmp/test_claude_config"
    settings.cli.enable_cli_hooks = True
    settings.cli.cli_polling_interval_seconds = 0.1  # 快速测试
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


class TestFileWatchCollector:
    """文件监听采集器测试"""

    @pytest.mark.asyncio
    async def test_file_watch_collector_no_directory(self, collector):
        """测试监听不存在的目录"""
        collector.cli_log_path = Path("/tmp/non_existent_directory")
        
        # 模拟is_running为True以便进入监听逻辑
        collector.is_running = True
        
        conversations = await collector._file_watch_collector()
        
        # 应该返回空列表并记录警告
        assert conversations == []

    @pytest.mark.asyncio
    async def test_file_watch_collector_with_log_files(self, collector):
        """测试监听包含日志文件的目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir)
            collector.is_running = True
            
            # 创建测试日志文件
            log_file = collector.cli_log_path / "test.log"
            log_file.write_text("[2024-01-06 10:30:45] USER: Test message\n")
            
            # 模拟文件监听只触发一次变化
            async def mock_awatch(*args, **kwargs):
                # 模拟文件被修改的事件
                from watchfiles import Change
                yield [(Change.modified, str(log_file))]
                # 结束监听
                collector.is_running = False
            
            with patch('claude_memory.collectors.conversation_collector.awatch', mock_awatch):
                with patch.object(collector, '_process_log_file', return_value=[Mock()]) as mock_process:
                    conversations = await collector._file_watch_collector()
            
            # 验证处理了文件
            mock_process.assert_called_once_with(log_file)

    @pytest.mark.asyncio
    async def test_file_watch_collector_filters_file_types(self, collector):
        """测试文件类型过滤"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir)
            collector.is_running = True
            
            # 创建不同类型的文件
            log_file = collector.cli_log_path / "test.log"
            jsonl_file = collector.cli_log_path / "test.jsonl"
            txt_file = collector.cli_log_path / "test.txt"
            other_file = collector.cli_log_path / "test.pdf"
            
            log_file.write_text("log content")
            jsonl_file.write_text("jsonl content")
            txt_file.write_text("txt content")
            other_file.write_text("pdf content")
            
            # 模拟文件监听触发所有文件变化
            async def mock_awatch(*args, **kwargs):
                from watchfiles import Change
                yield [
                    (Change.modified, str(log_file)),
                    (Change.modified, str(jsonl_file)),
                    (Change.modified, str(txt_file)),
                    (Change.modified, str(other_file)),
                ]
                collector.is_running = False
            
            with patch('claude_memory.collectors.conversation_collector.awatch', mock_awatch):
                with patch.object(collector, '_process_log_file', return_value=[]) as mock_process:
                    await collector._file_watch_collector()
            
            # 验证只处理了指定类型的文件（.log, .jsonl, .txt）
            processed_files = [call[0][0] for call in mock_process.call_args_list]
            assert log_file in processed_files
            assert jsonl_file in processed_files
            assert txt_file in processed_files
            assert other_file not in processed_files

    @pytest.mark.asyncio
    async def test_file_watch_collector_handles_file_added(self, collector):
        """测试处理新增文件事件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir)
            collector.is_running = True
            
            log_file = collector.cli_log_path / "new_file.log"
            
            # 模拟文件被添加的事件
            async def mock_awatch(*args, **kwargs):
                from watchfiles import Change
                yield [(Change.added, str(log_file))]
                collector.is_running = False
            
            with patch('claude_memory.collectors.conversation_collector.awatch', mock_awatch):
                with patch.object(collector, '_process_log_file', return_value=[Mock()]) as mock_process:
                    await collector._file_watch_collector()
            
            # 验证处理了新增文件
            mock_process.assert_called_once_with(log_file)

    @pytest.mark.asyncio
    async def test_file_watch_collector_ignores_deleted_files(self, collector):
        """测试忽略删除文件事件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir)
            collector.is_running = True
            
            log_file = collector.cli_log_path / "deleted_file.log"
            
            # 模拟文件被删除的事件
            async def mock_awatch(*args, **kwargs):
                from watchfiles import Change
                yield [(Change.deleted, str(log_file))]
                collector.is_running = False
            
            with patch('claude_memory.collectors.conversation_collector.awatch', mock_awatch):
                with patch.object(collector, '_process_log_file') as mock_process:
                    await collector._file_watch_collector()
            
            # 验证没有处理删除的文件
            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_file_watch_collector_stops_when_not_running(self, collector):
        """测试监听器在停止状态时退出"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir)
            collector.is_running = False  # 设置为停止状态
            
            # 模拟文件监听
            async def mock_awatch(*args, **kwargs):
                # 永远不yield任何事件，因为is_running=False应该立即退出
                yield []
            
            with patch('claude_memory.collectors.conversation_collector.awatch', mock_awatch):
                conversations = await collector._file_watch_collector()
            
            assert conversations == []

    @pytest.mark.asyncio
    async def test_file_watch_collector_error_handling(self, collector):
        """测试文件监听错误处理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir)
            collector.is_running = True
            
            # 模拟awatch抛出异常
            async def mock_awatch(*args, **kwargs):
                raise PermissionError("Permission denied")
            
            with patch('claude_memory.collectors.conversation_collector.awatch', mock_awatch):
                with pytest.raises(Exception):  # 应该重新抛出为RetryableError
                    await collector._file_watch_collector()


class TestPollingCollector:
    """轮询采集器测试"""

    @pytest.mark.asyncio
    async def test_polling_collector_basic_flow(self, collector):
        """测试轮询采集器基本流程"""
        collector.is_running = True
        collector.polling_interval = 0.01  # 很短的间隔用于测试
        
        # 模拟CLI状态检查
        cli_status_responses = [
            {'active_sessions': ['session-1']},
            {'active_sessions': []},  # 第二次查询时没有活跃会话
        ]
        
        call_count = 0
        async def mock_check_cli_status():
            nonlocal call_count
            response = cli_status_responses[min(call_count, len(cli_status_responses) - 1)]
            call_count += 1
            # 在第二次调用后停止
            if call_count >= 2:
                collector.is_running = False
            return response
        
        with patch.object(collector, '_check_cli_status', mock_check_cli_status):
            with patch.object(collector, '_collect_session_data', return_value=[Mock()]) as mock_collect:
                conversations = await collector._polling_collector()
        
        # 验证调用了会话数据收集
        mock_collect.assert_called_with('session-1')
        assert isinstance(conversations, list)

    @pytest.mark.asyncio
    async def test_polling_collector_no_active_sessions(self, collector):
        """测试没有活跃会话时的轮询"""
        collector.is_running = True
        collector.polling_interval = 0.01
        
        call_count = 0
        async def mock_check_cli_status():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                collector.is_running = False
            return {'active_sessions': []}
        
        with patch.object(collector, '_check_cli_status', mock_check_cli_status):
            with patch.object(collector, '_collect_session_data') as mock_collect:
                conversations = await collector._polling_collector()
        
        # 验证没有调用会话数据收集
        mock_collect.assert_not_called()
        assert conversations == []

    @pytest.mark.asyncio
    async def test_polling_collector_error_recovery(self, collector):
        """测试轮询采集器错误恢复"""
        collector.is_running = True
        collector.polling_interval = 0.01
        
        call_count = 0
        async def mock_check_cli_status():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary error")
            elif call_count >= 2:
                collector.is_running = False
                return {'active_sessions': []}
            return {'active_sessions': []}
        
        with patch.object(collector, '_check_cli_status', mock_check_cli_status):
            # 不应该抛出异常，应该继续运行
            conversations = await collector._polling_collector()
        
        assert conversations == []
        assert call_count >= 2  # 确认错误后继续运行

    @pytest.mark.asyncio
    async def test_polling_collector_multiple_sessions(self, collector):
        """测试处理多个活跃会话"""
        collector.is_running = True
        collector.polling_interval = 0.01
        
        async def mock_check_cli_status():
            collector.is_running = False  # 一次检查后停止
            return {'active_sessions': ['session-1', 'session-2', 'session-3']}
        
        mock_conversations = [Mock(), Mock(), Mock()]
        async def mock_collect_session_data(session_id):
            return [mock_conversations.pop(0)] if mock_conversations else []
        
        with patch.object(collector, '_check_cli_status', mock_check_cli_status):
            with patch.object(collector, '_collect_session_data', mock_collect_session_data) as mock_collect:
                conversations = await collector._polling_collector()
        
        # 验证为每个会话都调用了数据收集
        assert mock_collect.call_count == 3
        assert len(conversations) == 3


class TestCLIStatusChecking:
    """CLI状态检查测试"""

    @pytest.mark.asyncio
    async def test_check_cli_status_with_config_file(self, collector):
        """测试有配置文件时的状态检查"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.config_path = Path(temp_dir)
            collector.cli_log_path = Path(temp_dir) / "logs"
            
            # 创建状态配置文件
            status_file = collector.config_path / "status.json"
            status_data = {
                "is_running": True,
                "active_sessions": ["session-1", "session-2"],
                "last_activity": "2024-01-06T10:30:45"
            }
            status_file.write_text(str(status_data).replace("'", '"'))
            
            status = await collector._check_cli_status()
            
            assert status['active_sessions'] == ["session-1", "session-2"]

    @pytest.mark.asyncio
    async def test_check_cli_status_with_recent_log_files(self, collector):
        """测试通过日志文件检测活跃会话"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir)
            collector.config_path = Path("/tmp/non_existent")  # 配置文件不存在
            
            # 创建最近修改的日志文件
            recent_log = collector.cli_log_path / "session_f47ac10b-58cc-4372-a567-0e02b2c3d479.log"
            recent_log.write_text("recent content")
            
            # 创建旧的日志文件
            old_log = collector.cli_log_path / "session_old-session-id.log"
            old_log.write_text("old content")
            
            # 修改文件的修改时间来模拟旧文件
            import os
            old_timestamp = time.time() - 1000  # 1000秒前
            os.utime(old_log, (old_timestamp, old_timestamp))
            
            with patch.object(collector, '_is_file_recently_modified') as mock_recent:
                # 模拟最近修改检查结果
                def side_effect(file_path):
                    return file_path.name.startswith("session_f47ac10b")
                mock_recent.side_effect = side_effect
                
                status = await collector._check_cli_status()
            
            # 验证找到了活跃会话
            assert "f47ac10b-58cc-4372-a567-0e02b2c3d479" in status['active_sessions']
            assert status['is_running'] is True

    @pytest.mark.asyncio
    async def test_check_cli_status_no_activity(self, collector):
        """测试没有活动时的状态"""
        # 确保目录不存在
        collector.config_path = Path("/tmp/non_existent_config")
        collector.cli_log_path = Path("/tmp/non_existent_logs")
        
        status = await collector._check_cli_status()
        
        assert status['is_running'] is False
        assert status['active_sessions'] == []
        assert status['last_activity'] is None

    @pytest.mark.asyncio
    async def test_check_cli_status_error_handling(self, collector):
        """测试状态检查错误处理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.config_path = Path(temp_dir)
            
            # 创建无效的JSON配置文件
            status_file = collector.config_path / "status.json"
            status_file.write_text("invalid json content")
            
            # 不应该抛出异常
            status = await collector._check_cli_status()
            
            # 应该返回默认状态
            assert status['is_running'] is False
            assert status['active_sessions'] == []


class TestCollectionLifecycle:
    """采集生命周期测试"""

    @pytest.mark.asyncio
    async def test_start_collection_success(self, collector):
        """测试成功启动采集服务"""
        with patch.object(collector, '_validate_cli_environment', return_value=True):
            # 模拟采集任务快速完成
            async def mock_file_watch():
                await asyncio.sleep(0.01)
                return []
            
            async def mock_polling():
                await asyncio.sleep(0.01)
                return []
            
            with patch.object(collector, '_file_watch_collector', mock_file_watch):
                with patch.object(collector, '_polling_collector', mock_polling):
                    # 在另一个任务中停止采集
                    async def stop_after_delay():
                        await asyncio.sleep(0.02)
                        collector.is_running = False
                    
                    stop_task = asyncio.create_task(stop_after_delay())
                    result = await collector.start_collection()
                    await stop_task
        
        assert result is True

    @pytest.mark.asyncio
    async def test_start_collection_already_running(self, collector):
        """测试重复启动采集服务"""
        collector.is_running = True
        
        result = await collector.start_collection()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_start_collection_validation_failure(self, collector):
        """测试环境验证失败时的启动"""
        with patch.object(collector, '_validate_cli_environment', return_value=False):
            with pytest.raises(RuntimeError, match="Claude CLI environment validation failed"):
                await collector.start_collection()

    @pytest.mark.asyncio
    async def test_stop_collection(self, collector):
        """测试停止采集服务"""
        collector.is_running = True
        collector.conversation_cache["session-1"] = Mock()
        
        with patch.object(collector, '_flush_conversation_cache') as mock_flush:
            await collector.stop_collection()
        
        assert collector.is_running is False
        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_collection_integration_flow(self, collector):
        """测试完整采集流程集成"""
        with tempfile.TemporaryDirectory() as temp_dir:
            collector.cli_log_path = Path(temp_dir)
            collector.config_path = Path(temp_dir) / "config"
            collector.config_path.mkdir()
            
            # 创建测试日志文件
            log_file = collector.cli_log_path / "test_session.log"
            log_file.write_text("[2024-01-06 10:30:45] USER: Test message\n")
            
            # 快速停止采集以便测试完成
            async def stop_soon():
                await asyncio.sleep(0.05)
                collector.is_running = False
            
            with patch.object(collector, '_should_include_entry', return_value=True):
                with patch.object(collector.text_processor, 'clean_and_normalize', side_effect=lambda x: x):
                    with patch.object(collector.text_processor, 'count_tokens', return_value=5):
                        stop_task = asyncio.create_task(stop_soon())
                        result = await collector.start_collection()
                        await stop_task
            
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])