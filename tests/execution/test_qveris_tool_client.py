from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.qveris import (
    QverisProtocolError,
    QverisToolClient,
    execute_discovered_tool,
    public_response_shape,
)


def _store(tmp_path: Path) -> RawArtifactStore:
    return RawArtifactStore(tmp_path / "raw", tmp_path / "repo")


def test_ac_qveris_tool_execution_uses_the_search_bound_tool_call(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            assert request.headers["Authorization"] == "Bearer controlled-key"
            if request.url.path == "/api/v1/search":
                assert json.loads(request.content) == {
                    "query": "ETF holdings",
                    "limit": 5,
                }
                return httpx.Response(
                    200, json={"search_id": "search-123", "results": []}
                )
            assert request.url.path == "/api/v1/tools/execute"
            assert request.url.params["tool_id"] == "frozen-tool"
            assert json.loads(request.content) == {
                "search_id": "search-123",
                "parameters": {"symbol": "SPY"},
                "max_response_size": 65536,
            }
            return httpx.Response(200, json={"data": []})

        client = QverisToolClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            _store(tmp_path),
            "controlled-key",
        )
        search = await client.search("search", "ETF holdings", limit=5)
        result = await client.execute(
            "execute", "frozen-tool", search.search_id, {"symbol": "SPY"}
        )

        assert len(calls) == 2
        assert search.result.raw_path.exists()
        assert result.raw_path.exists()
        await client.close()

    asyncio.run(run())


def test_ac_qveris_tool_description_uses_only_frozen_ids(tmp_path: Path) -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/tools/by-ids"
            assert json.loads(request.content) == {
                "tool_ids": ["frozen-tool", "another-frozen-tool"]
            }
            return httpx.Response(200, json={"tools": []})

        client = QverisToolClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            _store(tmp_path),
            "controlled-key",
        )
        result = await client.describe_tools(
            "describe", ("frozen-tool", "another-frozen-tool")
        )

        assert result.raw_path.exists()
        await client.close()

    asyncio.run(run())


def test_ac_qveris_direct_execution_rejects_a_tool_absent_from_discovery(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, json={"search_id": "search-123", "results": []})

        client = QverisToolClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            _store(tmp_path),
            "controlled-key",
        )
        try:
            with pytest.raises(QverisProtocolError, match="not returned by discovery"):
                await execute_discovered_tool(
                    client,
                    "search",
                    "ETF holdings",
                    "frozen-tool",
                    {"symbol": "SPY"},
                )
        finally:
            await client.close()

        assert len(calls) == 1, "AC Direct execution must not call an unbound tool"

    asyncio.run(run())


def test_ac_qveris_response_shape_exposes_no_provider_values() -> None:
    shape = public_response_shape(
        {
            "data": {"symbol": "SPY", "holdings": [{"ticker": "AAPL"}]},
            "request_id": "private-request-id",
        }
    )

    assert shape == {
        "type": "object",
        "keys": ["data", "request_id"],
        "fields": {
            "data": {
                "type": "object",
                "keys": ["holdings", "symbol"],
                "fields": {
                    "holdings": {"type": "array", "length": 1},
                    "symbol": {"type": "string"},
                },
            },
            "request_id": {"type": "string"},
        },
    }
    assert "SPY" not in repr(shape)
    assert "AAPL" not in repr(shape)
    assert "private-request-id" not in repr(shape)
