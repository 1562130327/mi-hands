"""
重试工具 - 通用重试机制

提供带指数退避的重试功能，用于 API 调用等不稳定操作
"""

import time
import functools
from typing import Callable, Any, Optional, Type


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    带指数退避的重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数退避基数
        retryable_exceptions: 可重试的异常类型
        on_retry: 重试时的回调函数（可选）

    Example:
        @retry_with_backoff(max_retries=3)
        def call_api():
            return requests.get("https://api.example.com")
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # 最后一次尝试失败，抛出异常
                        raise last_exception

                    # 计算延迟
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # 调用回调
                    if on_retry:
                        on_retry(attempt + 1, delay, e)

                    # 等待
                    time.sleep(delay)

            # 不应该到达这里，但为了类型检查
            raise last_exception

        return wrapper
    return decorator


def retry_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
    **kwargs,
) -> Any:
    """
    带重试的函数调用

    Args:
        func: 要调用的函数
        *args: 位置参数
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数退避基数
        retryable_exceptions: 可重试的异常类型
        on_retry: 重试时的回调函数（可选）
        **kwargs: 关键字参数

    Returns:
        函数返回值

    Example:
        result = retry_call(
            api.call,
            max_retries=3,
            base_delay=1.0,
        )
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e

            if attempt == max_retries:
                raise last_exception

            # 计算延迟
            delay = min(
                base_delay * (exponential_base ** attempt),
                max_delay
            )

            # 调用回调
            if on_retry:
                on_retry(attempt + 1, delay, e)

            # 等待
            time.sleep(delay)

    raise last_exception


class RetryContext:
    """
    重试上下文管理器

    用于需要在重试时执行特定逻辑的场景

    Example:
        with RetryContext(max_retries=3) as ctx:
            while ctx.should_retry():
                try:
                    result = call_api()
                    ctx.mark_success()
                    break
                except Exception as e:
                    ctx.mark_failure(e)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.attempt = 0
        self.last_exception = None
        self._success = False

    def should_retry(self) -> bool:
        """是否应该重试"""
        return self.attempt <= self.max_retries and not self._success

    def mark_success(self):
        """标记成功"""
        self._success = True

    def mark_failure(self, exception: Exception):
        """标记失败"""
        self.last_exception = exception
        self.attempt += 1

    def get_delay(self) -> float:
        """获取当前延迟时间"""
        if self.attempt == 0:
            return 0
        return min(
            self.base_delay * (2 ** (self.attempt - 1)),
            self.max_delay
        )

    def wait(self):
        """等待"""
        delay = self.get_delay()
        if delay > 0:
            time.sleep(delay)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
