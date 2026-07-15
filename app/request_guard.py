import asyncio
import math
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from dotenv import load_dotenv


# 必须在读取环境变量之前加载.env
load_dotenv()

def read_positive_int(
    environment_name: str,
    default: int,
) -> int:
    """读取正整数环境变量，配置错误时使用默认值。"""

    raw_value = os.getenv(environment_name)

    if raw_value is None:
        return default

    try:
        parsed_value = int(raw_value)
    except ValueError:
        return default

    if parsed_value <= 0:
        return default

    return parsed_value


@dataclass(frozen=True)
class RateLimitDecision:
    """一次限流检查的结果。"""

    allowed: bool
    remaining: int
    retry_after: int = 0
    scope: str = ""


class SlidingWindowLimiter:
    """基于滑动时间窗口的内存限流器。"""

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        if max_requests <= 0:
            raise ValueError(
                "max_requests 必须大于0。"
            )

        if window_seconds <= 0:
            raise ValueError(
                "window_seconds 必须大于0。"
            )

        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self._request_times: dict[
            str,
            deque[float],
        ] = {}

        self._lock = asyncio.Lock()
        self._check_count = 0

    def _remove_expired_requests(
        self,
        request_times: deque[float],
        now: float,
    ) -> None:
        """删除已经离开时间窗口的请求时间。"""

        cutoff_time = (
            now - self.window_seconds
        )

        while (
            request_times
            and request_times[0] <= cutoff_time
        ):
            request_times.popleft()

    def _cleanup_empty_keys(
        self,
        now: float,
    ) -> None:
        """定期清理长时间未使用的访问者记录。"""

        empty_keys: list[str] = []

        for key, request_times in (
            self._request_times.items()
        ):
            self._remove_expired_requests(
                request_times,
                now,
            )

            if not request_times:
                empty_keys.append(key)

        for key in empty_keys:
            self._request_times.pop(
                key,
                None,
            )

    async def check(
        self,
        key: str,
    ) -> RateLimitDecision:
        """检查并记录一次请求。"""

        normalized_key = (
            key.strip() or "unknown"
        )

        now = time.monotonic()

        async with self._lock:
            self._check_count += 1

            # 避免访问者数量增加后字典无限增长。
            if self._check_count % 100 == 0:
                self._cleanup_empty_keys(now)

            request_times = (
                self._request_times.setdefault(
                    normalized_key,
                    deque(),
                )
            )

            self._remove_expired_requests(
                request_times,
                now,
            )

            if (
                len(request_times)
                >= self.max_requests
            ):
                oldest_request = (
                    request_times[0]
                )

                retry_after = max(
                    1,
                    math.ceil(
                        oldest_request
                        + self.window_seconds
                        - now
                    ),
                )

                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    retry_after=retry_after,
                )

            request_times.append(now)

            return RateLimitDecision(
                allowed=True,
                remaining=(
                    self.max_requests
                    - len(request_times)
                ),
            )


class RequestLimiter:
    """同时检查IP频率和会话频率。"""

    def __init__(
        self,
        per_ip_per_minute: int,
        per_session_per_hour: int,
    ) -> None:
        self.ip_limiter = SlidingWindowLimiter(
            max_requests=per_ip_per_minute,
            window_seconds=60,
        )

        self.session_limiter = (
            SlidingWindowLimiter(
                max_requests=(
                    per_session_per_hour
                ),
                window_seconds=3600,
            )
        )

    async def check(
        self,
        ip_address: str,
        session_id: str,
    ) -> RateLimitDecision:
        """检查一次聊天请求能否继续执行。"""

        ip_decision = (
            await self.ip_limiter.check(
                ip_address
            )
        )

        if not ip_decision.allowed:
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                retry_after=(
                    ip_decision.retry_after
                ),
                scope="ip",
            )

        session_decision = (
            await self.session_limiter.check(
                session_id
            )
        )

        if not session_decision.allowed:
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                retry_after=(
                    session_decision.retry_after
                ),
                scope="session",
            )

        return RateLimitDecision(
            allowed=True,
            remaining=min(
                ip_decision.remaining,
                session_decision.remaining,
            ),
        )


class SessionBusyError(RuntimeError):
    """同一个会话已有请求正在执行。"""


class SessionConcurrencyGuard:
    """保证一个会话同一时间只运行一个请求。"""

    def __init__(self) -> None:
        self._active_sessions: set[str] = set()
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        session_id: str,
    ) -> None:
        """占用一个会话。"""

        async with self._lock:
            if (
                session_id
                in self._active_sessions
            ):
                raise SessionBusyError(
                    "该会话已有请求正在处理。"
                )

            self._active_sessions.add(
                session_id
            )

    async def release(
        self,
        session_id: str,
    ) -> None:
        """释放一个会话。"""

        async with self._lock:
            self._active_sessions.discard(
                session_id
            )

    @asynccontextmanager
    async def hold(
        self,
        session_id: str,
    ) -> AsyncIterator[None]:
        """在代码块执行期间占用指定会话。"""

        await self.acquire(session_id)

        try:
            yield
        finally:
            await self.release(session_id)


PER_IP_PER_MINUTE = read_positive_int(
    "RATE_LIMIT_PER_IP_PER_MINUTE",
    8,
)

PER_SESSION_PER_HOUR = read_positive_int(
    "RATE_LIMIT_PER_SESSION_PER_HOUR",
    40,
)


print(
    "[RATE LIMIT CONFIG] "
    f"per_ip_per_minute={PER_IP_PER_MINUTE}, "
    f"per_session_per_hour={PER_SESSION_PER_HOUR}"
)


request_limiter = RequestLimiter(
    per_ip_per_minute=PER_IP_PER_MINUTE,
    per_session_per_hour=(
        PER_SESSION_PER_HOUR
    ),
)

session_concurrency_guard = (
    SessionConcurrencyGuard()
)