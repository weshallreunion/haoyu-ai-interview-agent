import asyncio

from app.request_guard import (
    RequestLimiter,
    SessionBusyError,
    SessionConcurrencyGuard,
    SlidingWindowLimiter,
)


async def test_sliding_window() -> None:
    """测试滑动窗口是否能正确拒绝超额请求。"""

    limiter = SlidingWindowLimiter(
        max_requests=2,
        window_seconds=1,
    )

    first = await limiter.check("visitor-a")
    second = await limiter.check("visitor-a")
    third = await limiter.check("visitor-a")

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.retry_after >= 1

    await asyncio.sleep(1.1)

    fourth = await limiter.check("visitor-a")

    assert fourth.allowed is True

    print("[PASS] 滑动窗口限流")


async def test_separate_visitors() -> None:
    """测试不同访问者是否拥有独立额度。"""

    limiter = SlidingWindowLimiter(
        max_requests=1,
        window_seconds=60,
    )

    visitor_a = await limiter.check(
        "visitor-a"
    )

    visitor_b = await limiter.check(
        "visitor-b"
    )

    assert visitor_a.allowed is True
    assert visitor_b.allowed is True

    print("[PASS] 不同访问者独立计数")


async def test_request_limiter() -> None:
    """测试IP与会话两级限制。"""

    limiter = RequestLimiter(
        per_ip_per_minute=2,
        per_session_per_hour=1,
    )

    first = await limiter.check(
        "127.0.0.1",
        "session-a",
    )

    second = await limiter.check(
        "127.0.0.1",
        "session-a",
    )

    assert first.allowed is True
    assert second.allowed is False
    assert second.scope == "session"

    print("[PASS] IP和会话两级限流")


async def test_concurrency_guard() -> None:
    """测试同一会话是否会拒绝并发执行。"""

    guard = SessionConcurrencyGuard()

    await guard.acquire("session-a")

    try:
        try:
            await guard.acquire("session-a")
        except SessionBusyError:
            print(
                "[PASS] 同一会话并发保护"
            )
        else:
            raise AssertionError(
                "同一会话的第二次占用没有被拒绝。"
            )

    finally:
        await guard.release("session-a")

    # 释放以后应能重新占用。
    await guard.acquire("session-a")
    await guard.release("session-a")


async def main() -> None:
    await test_sliding_window()
    await test_separate_visitors()
    await test_request_limiter()
    await test_concurrency_guard()

    print("\n请求保护模块全部测试通过。")


if __name__ == "__main__":
    asyncio.run(main())