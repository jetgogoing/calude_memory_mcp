"""
Claude记忆管理MCP服务 - 对话采集器

负责捕获Claude CLI的输入输出对话，解析对话结构，并进行数据标准化。
支持多种捕获方式：文件监听、CLI Hook、WebSocket连接等。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union

import aiofiles
import httpx
import structlog
from watchfiles import awatch, Change
from pydantic import BaseModel, Field

from claude_memory.models.data_models import (
    ConversationModel,
    MessageModel,
    MessageType,
    ProcessingStatus,
)
from claude_memory.config.settings import get_settings
from claude_memory.utils.text_processing import TextProcessor
from claude_memory.utils.error_handling import handle_exceptions, RetryableError

logger = structlog.get_logger(__name__)


class CLILogEntry(BaseModel):
    """CLI日志条目模型"""
    
    timestamp: datetime
    message_type: MessageType
    content: str
    metadata: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    raw_line: str


class ConversationCollector:
    """
    对话采集器 - 负责从Claude CLI捕获对话数据
    
    功能特性:
    - 多种捕获方式：文件监听、CLI Hook、轮询
    - 实时对话解析和结构化
    - 数据标准化和验证
    - 错误恢复和容错处理
    - 性能优化和资源管理
    """
    
    def __init__(self, project_id: Optional[str] = None):
        self.settings = get_settings()
        self.text_processor = TextProcessor()
        self.is_running = False
        self.active_sessions: Set[str] = set()
        self.conversation_cache: Dict[str, ConversationModel] = {}
        self.last_processed_timestamp: Optional[datetime] = None
        
        # 项目ID配置 - 使用提供的project_id或默认值
        self.project_id = project_id or self.settings.project.default_project_id
        
        # CLI日志路径配置
        self.cli_log_path = Path(self.settings.cli.claude_cli_log_path).expanduser()
        self.config_path = Path(self.settings.cli.claude_cli_config_path).expanduser()
        
        # 性能配置
        self.batch_size = self.settings.performance.batch_size
        self.polling_interval = self.settings.cli.cli_polling_interval_seconds
        
        # API Server配置
        self.api_base_url = os.getenv("CLAUDE_MEMORY_API_URL", "http://localhost:8000")
        self.http_client: Optional[httpx.AsyncClient] = None
        
        logger.info(
            "ConversationCollector initialized",
            project_id=self.project_id,
            cli_log_path=str(self.cli_log_path),
            config_path=str(self.config_path),
            batch_size=self.batch_size,
            api_base_url=self.api_base_url,
        )

    @handle_exceptions(logger=logger, default_return=False)
    async def start_collection(self) -> bool:
        """
        启动对话采集服务
        
        Returns:
            bool: 启动是否成功
        """
        if self.is_running:
            logger.warning("ConversationCollector is already running")
            return False
            
        try:
            self.is_running = True
            
            # 初始化HTTP客户端
            self.http_client = httpx.AsyncClient(
                base_url=self.api_base_url,
                timeout=httpx.Timeout(30.0),
                headers={"Content-Type": "application/json"}
            )
            
            # 验证API Server连接
            try:
                response = await self.http_client.get("/health")
                if response.status_code == 200:
                    logger.info("Successfully connected to API Server")
                else:
                    logger.warning(f"API Server health check returned {response.status_code}")
            except Exception as e:
                logger.error(f"Failed to connect to API Server: {e}")
                # 继续运行，收集的对话将缓存在本地
            
            # 验证CLI环境
            if not await self._validate_cli_environment():
                raise RuntimeError("Claude CLI environment validation failed")
            
            # 启动多种采集方式
            collection_tasks = []
            
            if self.settings.cli.enable_cli_hooks:
                # 文件监听方式
                collection_tasks.append(
                    asyncio.create_task(self._file_watch_collector())
                )
                
                # 轮询备份方式
                collection_tasks.append(
                    asyncio.create_task(self._polling_collector())
                )
            
            logger.info(
                "ConversationCollector started",
                collection_methods=len(collection_tasks)
            )
            
            # 并发运行所有采集任务
            await asyncio.gather(*collection_tasks, return_exceptions=True)
            
            return True
            
        except Exception as e:
            logger.error("Failed to start ConversationCollector", error=str(e))
            self.is_running = False
            raise

    @handle_exceptions(logger=logger)
    async def stop_collection(self) -> None:
        """停止对话采集服务"""
        self.is_running = False
        
        # 保存缓存中的对话
        await self._flush_conversation_cache()
        
        logger.info("ConversationCollector stopped")

    @handle_exceptions(logger=logger, default_return=[])
    async def _file_watch_collector(self) -> List[ConversationModel]:
        """
        文件监听采集器 - 监听CLI日志文件变化
        
        Returns:
            List[ConversationModel]: 采集到的对话列表
        """
        conversations = []
        
        if not self.cli_log_path.exists():
            logger.warning(
                "CLI log path does not exist",
                path=str(self.cli_log_path)
            )
            return conversations
        
        try:
            async for changes in awatch(self.cli_log_path, recursive=True):
                if not self.is_running:
                    break
                
                for change_type, file_path in changes:
                    if change_type in (Change.added, Change.modified):
                        file_path = Path(file_path)
                        
                        # 只处理日志文件
                        if file_path.suffix in ('.log', '.jsonl', '.txt'):
                            new_conversations = await self._process_log_file(file_path)
                            conversations.extend(new_conversations)
            
        except Exception as e:
            logger.error("File watch collector error", error=str(e))
            raise RetryableError(f"File watch error: {str(e)}")
        
        return conversations

    @handle_exceptions(logger=logger, default_return=[])
    async def _polling_collector(self) -> List[ConversationModel]:
        """
        轮询采集器 - 定期检查CLI状态和日志
        
        Returns:
            List[ConversationModel]: 采集到的对话列表
        """
        conversations = []
        
        while self.is_running:
            try:
                # 检查CLI进程状态
                cli_status = await self._check_cli_status()
                
                if cli_status.get('active_sessions'):
                    # 处理活跃会话
                    for session_id in cli_status['active_sessions']:
                        session_conversations = await self._collect_session_data(session_id)
                        conversations.extend(session_conversations)
                
                # 等待下一次轮询
                await asyncio.sleep(self.polling_interval)
                
            except Exception as e:
                logger.error("Polling collector error", error=str(e))
                await asyncio.sleep(self.polling_interval * 2)  # 延长等待时间
        
        return conversations

    @handle_exceptions(logger=logger, default_return={})
    async def _check_cli_status(self) -> Dict[str, Any]:
        """
        检查Claude CLI状态
        
        Returns:
            Dict[str, Any]: CLI状态信息
        """
        status = {
            'is_running': False,
            'active_sessions': [],
            'last_activity': None,
        }
        
        try:
            # 检查CLI配置文件
            if self.config_path.exists():
                async with aiofiles.open(self.config_path / 'status.json', 'r') as f:
                    cli_config = json.loads(await f.read())
                    status.update(cli_config)
            
            # 检查活跃日志文件
            if self.cli_log_path.exists():
                log_files = list(self.cli_log_path.glob('*.log'))
                for log_file in log_files:
                    if await self._is_file_recently_modified(log_file):
                        session_id = self._extract_session_id_from_filename(log_file.name)
                        if session_id and session_id not in status['active_sessions']:
                            status['active_sessions'].append(session_id)
            
            status['is_running'] = len(status['active_sessions']) > 0
            
        except Exception as e:
            logger.warning("Failed to check CLI status", error=str(e))
        
        return status

    @handle_exceptions(logger=logger, default_return=[])
    async def _process_log_file(self, file_path: Path) -> List[ConversationModel]:
        """
        处理单个日志文件
        
        Args:
            file_path: 日志文件路径
            
        Returns:
            List[ConversationModel]: 解析出的对话列表
        """
        conversations = []
        
        try:
            # 读取文件内容
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # 解析日志内容
            log_entries = await self._parse_log_content(content, file_path.name)
            
            if not log_entries:
                return conversations
            
            # 按会话分组
            session_groups = self._group_entries_by_session(log_entries)
            
            # 转换为对话模型
            for session_id, entries in session_groups.items():
                conversation = await self._build_conversation_from_entries(
                    session_id, entries
                )
                if conversation:
                    conversations.append(conversation)
            
            logger.debug(
                "Processed log file",
                file_path=str(file_path),
                entries_count=len(log_entries),
                conversations_count=len(conversations),
            )
            
        except Exception as e:
            logger.error(
                "Failed to process log file",
                file_path=str(file_path),
                error=str(e)
            )
        
        return conversations

    @handle_exceptions(logger=logger, default_return=[])
    async def _parse_log_content(
        self, content: str, filename: str
    ) -> List[CLILogEntry]:
        """
        解析日志内容为结构化条目
        
        Args:
            content: 日志文件内容
            filename: 文件名
            
        Returns:
            List[CLILogEntry]: 解析后的日志条目列表
        """
        entries = []
        lines = content.strip().split('\n')
        
        # 提取会话ID（如果文件名包含）
        session_id = self._extract_session_id_from_filename(filename)
        
        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue
            
            try:
                entry = await self._parse_log_line(line, session_id)
                if entry:
                    entries.append(entry)
                    
            except Exception as e:
                logger.warning(
                    "Failed to parse log line",
                    filename=filename,
                    line_num=line_num,
                    line=line[:100],
                    error=str(e)
                )
        
        # 按时间排序
        entries.sort(key=lambda x: x.timestamp)
        
        return entries

    @handle_exceptions(logger=logger, default_return=None)
    async def _parse_log_line(
        self, line: str, default_session_id: Optional[str] = None
    ) -> Optional[CLILogEntry]:
        """
        解析单行日志
        
        Args:
            line: 日志行内容
            default_session_id: 默认会话ID
            
        Returns:
            Optional[CLILogEntry]: 解析后的日志条目
        """
        # 尝试多种日志格式
        
        # 格式1: JSON格式
        if line.strip().startswith('{'):
            try:
                data = json.loads(line)
                return CLILogEntry(
                    timestamp=datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat())),
                    message_type=MessageType(data.get('type', 'user')),
                    content=data.get('content', ''),
                    metadata=data.get('metadata'),
                    session_id=data.get('session_id') or default_session_id,
                    raw_line=line
                )
            except (json.JSONDecodeError, ValueError, KeyError):
                pass
        
        # 格式2: 结构化文本格式
        # 示例: [2024-01-06 10:30:45] USER: Hello Claude
        timestamp_pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(\w+):\s*(.*)'
        match = re.match(timestamp_pattern, line)
        
        if match:
            timestamp_str, message_type_str, content = match.groups()
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                message_type = MessageType(message_type_str.lower())
                
                return CLILogEntry(
                    timestamp=timestamp,
                    message_type=message_type,
                    content=content.strip(),
                    session_id=default_session_id,
                    raw_line=line
                )
            except (ValueError, KeyError):
                pass
        
        # 格式3: 简单文本格式 - 作为用户消息处理
        if len(line.strip()) >= self.settings.cli.min_conversation_length:
            return CLILogEntry(
                timestamp=datetime.utcnow(),
                message_type=MessageType.USER,
                content=line.strip(),
                session_id=default_session_id,
                raw_line=line
            )
        
        return None

    def _extract_session_id_from_filename(self, filename: str) -> Optional[str]:
        """
        从文件名提取会话ID
        
        Args:
            filename: 文件名
            
        Returns:
            Optional[str]: 会话ID
        """
        # 尝试多种文件名模式
        patterns = [
            r'session[_-]([a-f0-9\-]{36})',  # session_uuid
            r'claude[_-]([a-f0-9\-]{36})',  # claude_uuid
            r'chat[_-]([a-f0-9\-]{36})',    # chat_uuid
            r'([a-f0-9\-]{36})',            # 纯uuid
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # 如果没有找到UUID，使用文件名的哈希作为会话ID
        return hashlib.md5(filename.encode()).hexdigest()

    def _group_entries_by_session(
        self, entries: List[CLILogEntry]
    ) -> Dict[str, List[CLILogEntry]]:
        """
        按会话ID分组日志条目
        
        Args:
            entries: 日志条目列表
            
        Returns:
            Dict[str, List[CLILogEntry]]: 按会话分组的条目
        """
        groups = {}
        
        for entry in entries:
            session_id = entry.session_id or 'default'
            if session_id not in groups:
                groups[session_id] = []
            groups[session_id].append(entry)
        
        return groups

    @handle_exceptions(logger=logger, default_return=None)
    async def _build_conversation_from_entries(
        self, session_id: str, entries: List[CLILogEntry]
    ) -> Optional[ConversationModel]:
        """
        从日志条目构建对话模型
        
        Args:
            session_id: 会话ID
            entries: 日志条目列表
            
        Returns:
            Optional[ConversationModel]: 构建的对话模型
        """
        if not entries:
            return None
        
        # 过滤和验证条目
        valid_entries = []
        for entry in entries:
            # 应用过滤规则
            if await self._should_include_entry(entry):
                valid_entries.append(entry)
        
        if not valid_entries:
            return None
        
        # 构建消息列表
        messages = []
        for seq_num, entry in enumerate(valid_entries):
            # 处理消息内容
            processed_content = await self.text_processor.clean_and_normalize(
                entry.content
            )
            
            # 计算Token数量
            token_count = await self.text_processor.count_tokens(processed_content)
            
            message = MessageModel(
                conversation_id=uuid.UUID(int=hash(session_id) % (10**12)),  # 临时ID
                sequence_number=seq_num,
                message_type=entry.message_type,
                content=processed_content,
                metadata={
                    'original_timestamp': entry.timestamp.isoformat(),
                    'raw_line': entry.raw_line[:200],  # 保留部分原始内容用于调试
                    **(entry.metadata or {})
                },
                token_count=token_count,
                created_at=entry.timestamp
            )
            messages.append(message)
        
        # 构建对话模型
        total_tokens = sum(msg.token_count for msg in messages)
        
        conversation = ConversationModel(
            project_id=self.project_id,  # 添加project_id
            session_id=session_id,
            messages=messages,
            message_count=len(messages),
            token_count=total_tokens,
            status=ProcessingStatus.PENDING,
            created_at=valid_entries[0].timestamp,
            last_activity_at=valid_entries[-1].timestamp,
            metadata={
                'collector_version': '1.0',
                'source': 'file_watch',
                'original_entries_count': len(entries),
                'filtered_entries_count': len(valid_entries),
                'project_id': self.project_id,  # 在metadata中也记录project_id
            }
        )
        
        # 生成对话标题
        conversation.title = await self._generate_conversation_title(conversation)
        
        logger.debug(
            "Built conversation from entries",
            session_id=session_id,
            messages_count=len(messages),
            total_tokens=total_tokens,
        )
        
        # 立即发送到API Server
        if await self._send_conversation_to_api(conversation):
            logger.info("Conversation sent to API Server immediately")
        else:
            # 如果发送失败，加入缓存
            self.conversation_cache[session_id] = conversation
            logger.warning("Failed to send conversation, added to cache")
        
        return conversation

    async def _should_include_entry(self, entry: CLILogEntry) -> bool:
        """
        判断是否应该包含某个日志条目
        
        Args:
            entry: 日志条目
            
        Returns:
            bool: 是否包含
        """
        settings = self.settings.cli
        
        # 长度检查
        if len(entry.content) < settings.min_conversation_length:
            return False
        
        if len(entry.content) > settings.max_conversation_length:
            return False
        
        # 系统消息过滤
        if settings.exclude_system_messages and entry.message_type == MessageType.SYSTEM:
            return False
        
        # 时间过滤（可选）
        if self.last_processed_timestamp:
            if entry.timestamp <= self.last_processed_timestamp:
                return False
        
        # 内容质量检查
        if not await self.text_processor.is_content_meaningful(entry.content):
            return False
        
        return True

    async def _generate_conversation_title(
        self, conversation: ConversationModel
    ) -> str:
        """
        生成对话标题
        
        Args:
            conversation: 对话模型
            
        Returns:
            str: 生成的标题
        """
        if not conversation.messages:
            return f"Empty Conversation {conversation.session_id[:8]}"
        
        # 使用第一条用户消息作为标题基础
        first_user_message = None
        for msg in conversation.messages:
            if msg.message_type == MessageType.USER:
                first_user_message = msg
                break
        
        if first_user_message:
            # 提取前50个字符作为标题
            title = first_user_message.content[:50].strip()
            # 清理标题
            title = re.sub(r'\s+', ' ', title)
            if len(title) < len(first_user_message.content):
                title += "..."
            return title
        
        # 回退到时间戳标题
        return f"Conversation {conversation.created_at.strftime('%Y-%m-%d %H:%M')}"

    async def _validate_cli_environment(self) -> bool:
        """
        验证Claude CLI环境
        
        Returns:
            bool: 环境是否有效
        """
        try:
            # 检查日志目录
            if not self.cli_log_path.exists():
                logger.warning(
                    "CLI log directory does not exist, creating it",
                    path=str(self.cli_log_path)
                )
                self.cli_log_path.mkdir(parents=True, exist_ok=True)
            
            # 检查配置目录
            if not self.config_path.exists():
                logger.warning(
                    "CLI config directory does not exist",
                    path=str(self.config_path)
                )
                # 这不是致命错误，CLI可能使用不同的配置路径
            
            # 检查权限
            if not os.access(self.cli_log_path, os.R_OK):
                logger.error(
                    "No read permission for CLI log directory",
                    path=str(self.cli_log_path)
                )
                return False
            
            logger.info("CLI environment validation passed")
            return True
            
        except Exception as e:
            logger.error("CLI environment validation failed", error=str(e))
            return False

    async def _is_file_recently_modified(
        self, file_path: Path, threshold_seconds: int = 300
    ) -> bool:
        """
        检查文件是否最近被修改
        
        Args:
            file_path: 文件路径
            threshold_seconds: 阈值秒数
            
        Returns:
            bool: 是否最近被修改
        """
        try:
            if not file_path.exists():
                return False
            
            stat = file_path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            now = datetime.utcnow()
            
            return (now - mtime).total_seconds() <= threshold_seconds
            
        except Exception:
            return False

    async def _collect_session_data(self, session_id: str) -> List[ConversationModel]:
        """
        收集特定会话的数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            List[ConversationModel]: 会话数据
        """
        conversations = []
        
        try:
            # 查找相关的日志文件
            session_files = list(self.cli_log_path.glob(f"*{session_id}*"))
            
            for file_path in session_files:
                if file_path.is_file():
                    file_conversations = await self._process_log_file(file_path)
                    conversations.extend(file_conversations)
            
        except Exception as e:
            logger.error(
                "Failed to collect session data",
                session_id=session_id,
                error=str(e)
            )
        
        return conversations

    async def _flush_conversation_cache(self) -> None:
        """刷新对话缓存"""
        if self.conversation_cache:
            logger.info(
                "Flushing conversation cache",
                cached_conversations=len(self.conversation_cache)
            )
            # 将缓存的对话发送到API Server
            for session_id, conversation in self.conversation_cache.items():
                await self._send_conversation_to_api(conversation)
            self.conversation_cache.clear()
    
    async def _send_conversation_to_api(self, conversation: ConversationModel) -> bool:
        """
        将对话发送到API Server
        
        Args:
            conversation: 对话模型
            
        Returns:
            bool: 是否发送成功
        """
        if not self.http_client:
            logger.warning("HTTP client not initialized, caching conversation locally")
            return False
        
        try:
            # 准备请求数据
            request_data = {
                "project_id": self.project_id,
                "session_id": conversation.session_id,
                "title": conversation.title,
                "messages": [
                    {
                        "message_type": msg.message_type.value,
                        "content": msg.content,
                        "metadata": msg.metadata,
                        "timestamp": msg.created_at.isoformat()
                    }
                    for msg in conversation.messages
                ],
                "metadata": conversation.metadata
            }
            
            # 发送到API Server
            response = await self.http_client.post(
                "/conversation/store",
                json=request_data
            )
            
            if response.status_code == 200:
                logger.info(
                    "Successfully sent conversation to API Server",
                    session_id=conversation.session_id,
                    message_count=len(conversation.messages)
                )
                return True
            else:
                logger.error(
                    "Failed to send conversation to API Server",
                    session_id=conversation.session_id,
                    status_code=response.status_code,
                    response=response.text
                )
                return False
                
        except Exception as e:
            logger.error(
                "Error sending conversation to API Server",
                session_id=conversation.session_id,
                error=str(e)
            )
            return False