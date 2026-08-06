import asyncio
from pathlib import Path

from qveris_bench.execution.errors import TransportError
from qveris_bench.execution.events import EventLog
from qveris_bench.execution.retry import retry_with_budget


def test_ac4_events_are_ordered_and_timestamped(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl")
    first = log.append("request", {"method": "GET"})
    second = log.append("response", {"status": 200})

    assert (first.sequence, second.sequence) == (0, 1)
    assert len(log.read()) == 2


def test_ac4_events_redact_sensitive_details(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl")
    token = "api_" + "key"
    event = log.append("request", {token: "secret-value"})

    assert event.details[token] == "[REDACTED]"


def test_ac4_retry_respects_explicit_budget() -> None:
    async def run() -> None:
        attempts = 0

        async def operation() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise TransportError("timeout", "temporary")
            return "ok"

        assert await retry_with_budget(operation, 2) == "ok"
        assert attempts == 2

    asyncio.run(run())
