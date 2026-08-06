from __future__ import annotations

from collections.abc import Awaitable, Callable

from qveris_bench.execution.errors import TransportError

_RETRYABLE_CODES = {"timeout", "network_error", "rate_limited"}


async def retry_with_budget[T](
    operation: Callable[[], Awaitable[T]], attempts: int
) -> T:
    if attempts < 1:
        raise ValueError("retry attempts must be at least one")
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await operation()
        except TransportError as exc:
            if exc.code not in _RETRYABLE_CODES:
                raise
            last_error = exc
    assert last_error is not None
    raise last_error
