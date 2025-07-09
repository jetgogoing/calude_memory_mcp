"""
Claude记忆管理MCP服务 - 错误处理工具

提供统一的错误处理、重试机制、异常装饰器等功能。
"""

from __future__ import annotations

import asyncio
import functools
import logging
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    after_log,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class ClaudeMemoryError(Exception):
    """Claude记忆服务基础异常类"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.recoverable = recoverable
        self.timestamp = datetime.utcnow()


class RetryableError(ClaudeMemoryError):
    """可重试的错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class NonRetryableError(ClaudeMemoryError):
    """不可重试的错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, recoverable=False, **kwargs)


class ConfigurationError(NonRetryableError):
    """配置错误"""
    pass


class ValidationError(NonRetryableError):
    """数据验证错误"""
    pass


class ResourceNotFoundError(NonRetryableError):
    """资源未找到错误"""
    pass


class ResourceExhaustedError(RetryableError):
    """资源耗尽错误（如API限额）"""
    pass


class ExternalServiceError(RetryableError):
    """外部服务错误"""
    pass


class DatabaseError(RetryableError):
    """数据库错误"""
    pass


class NetworkError(RetryableError):
    """网络错误"""
    pass


class ProcessingError(RetryableError):
    """数据处理错误"""
    pass


class ServiceError(RetryableError):
    """服务错误"""
    pass


class SecurityError(NonRetryableError):
    """安全错误 - 权限验证失败等"""
    pass


class ErrorTracker:
    """错误追踪器 - 记录和分析错误模式"""
    
    def __init__(self, max_errors: int = 1000):
        self.max_errors = max_errors
        self.errors: List[Dict[str, Any]] = []
        self.error_counts: Dict[str, int] = {}
    
    def record_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录错误"""
        error_info = {
            'timestamp': datetime.utcnow(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_code': getattr(error, 'error_code', None),
            'recoverable': getattr(error, 'recoverable', False),
            'context': context or {},
            'traceback': traceback.format_exc()
        }
        
        self.errors.append(error_info)
        
        # 维护错误计数
        error_key = f"{error_info['error_type']}:{error_info['error_code']}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # 限制错误列表大小
        if len(self.errors) > self.max_errors:
            self.errors = self.errors[-self.max_errors:]
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        if not self.errors:
            return {
                'total_errors': 0,
                'unique_errors': 0,
                'most_common': [],
                'recent_errors': []
            }
        
        # 最常见的错误
        most_common = sorted(
            self.error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # 最近的错误
        recent_errors = self.errors[-10:]
        
        return {
            'total_errors': len(self.errors),
            'unique_errors': len(self.error_counts),
            'most_common': most_common,
            'recent_errors': [
                {
                    'timestamp': err['timestamp'].isoformat(),
                    'type': err['error_type'],
                    'message': err['error_message'][:100],
                    'recoverable': err['recoverable']
                }
                for err in recent_errors
            ]
        }


# 全局错误追踪器
global_error_tracker = ErrorTracker()


def handle_exceptions(
    *,
    logger: Optional[structlog.BoundLogger] = None,
    default_return: Any = None,
    reraise: bool = False,
    track_errors: bool = True
) -> Callable:
    """
    异常处理装饰器
    
    Args:
        logger: 日志记录器
        default_return: 发生异常时的默认返回值
        reraise: 是否重新抛出异常
        track_errors: 是否追踪错误
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'module': func.__module__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
                
                if track_errors:
                    global_error_tracker.record_error(e, context)
                
                if logger:
                    logger.error(
                        f"Exception in {func.__name__}",
                        error=str(e),
                        error_type=type(e).__name__,
                        **context
                    )
                
                if reraise:
                    raise
                
                return default_return
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'module': func.__module__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
                
                if track_errors:
                    global_error_tracker.record_error(e, context)
                
                if logger:
                    logger.error(
                        f"Exception in {func.__name__}",
                        error=str(e),
                        error_type=type(e).__name__,
                        **context
                    )
                
                if reraise:
                    raise
                
                return default_return
        
        # 返回适当的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def with_retry(
    *,
    max_attempts: int = 3,
    wait_min: float = 1.0,
    wait_max: float = 60.0,
    retry_exceptions: Optional[List[Type[Exception]]] = None,
    logger: Optional[structlog.BoundLogger] = None
) -> Callable:
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        wait_min: 最小等待时间（秒）
        wait_max: 最大等待时间（秒）
        retry_exceptions: 可重试的异常类型列表
        logger: 日志记录器
    """
    if retry_exceptions is None:
        retry_exceptions = [RetryableError, ExternalServiceError, NetworkError]
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            retry_logger = logger or structlog.get_logger(func.__module__)
            
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
                retry=retry_if_exception_type(tuple(retry_exceptions)),
                before_sleep=before_sleep_log(retry_logger, logging.INFO),
                after=after_log(retry_logger, logging.INFO)
            ):
                with attempt:
                    return await func(*args, **kwargs)
        
        # 对于同步函数，简单实现重试
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否是可重试的异常
                    if not any(isinstance(e, exc_type) for exc_type in retry_exceptions):
                        raise
                    
                    if attempt < max_attempts - 1:  # 不是最后一次尝试
                        wait_time = min(wait_min * (2 ** attempt), wait_max)
                        if logger:
                            logger.info(
                                f"Retrying {func.__name__} after {wait_time}s",
                                attempt=attempt + 1,
                                error=str(e)
                            )
                        asyncio.sleep(wait_time)
            
            # 所有重试都失败了
            if last_exception:
                raise last_exception
        
        # 返回适当的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """断路器 - 防止级联故障"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise ExternalServiceError("Circuit breaker is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise ExternalServiceError("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置断路器"""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.reset_timeout
    
    def _on_success(self) -> None:
        """成功时的处理"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self) -> None:
        """失败时的处理"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: List[datetime] = []
    
    async def acquire(self) -> bool:
        """获取执行许可"""
        now = datetime.utcnow()
        
        # 清理过期的调用记录
        cutoff_time = now.timestamp() - self.time_window
        self.calls = [
            call for call in self.calls
            if call.timestamp() > cutoff_time
        ]
        
        # 检查是否超过限制
        if len(self.calls) >= self.max_calls:
            return False
        
        # 记录当前调用
        self.calls.append(now)
        return True
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            if not await self.acquire():
                raise ResourceExhaustedError("Rate limit exceeded")
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # 对于同步函数，使用简化的检查
            if not asyncio.run(self.acquire()):
                raise ResourceExhaustedError("Rate limit exceeded")
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


def get_error_stats() -> Dict[str, Any]:
    """获取全局错误统计信息"""
    return global_error_tracker.get_error_stats()


def clear_error_stats() -> None:
    """清空错误统计信息"""
    global_error_tracker.errors.clear()
    global_error_tracker.error_counts.clear()