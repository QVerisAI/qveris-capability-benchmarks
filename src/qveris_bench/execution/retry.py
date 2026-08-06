from __future__ import annotations

from collections.abc import Awaitable, Callable


async def retry_with_budget[T](
    operation: Callable[[], Awaitable[T]], attempts: int
) -> T:
    if attempts < 1:
        raise ValueError("retry attempts must be at least one")
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
    assert last_error is not None
    raise last_error
