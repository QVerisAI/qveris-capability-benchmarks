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
    gateway_metrics,
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


def test_ac_gateway_metrics_extract_latency_and_cost() -> None:
    document = {
        "elapsed_time_ms": 1245,
        "cost": 2.42,
        "remaining_credits": 601776.39,
        "result": {"data": []},
    }

    latency_ms, cost_credits = gateway_metrics(document)

    assert latency_ms == 1245.0
    assert cost_credits == 2.42


def test_ac_gateway_metrics_reject_non_finite_or_missing_values() -> None:
    assert gateway_metrics({}) == (None, None)
    assert gateway_metrics({"elapsed_time_ms": 0, "cost": -1}) == (None, None)
    assert gateway_metrics({"elapsed_time_ms": "fast", "cost": True}) == (None, None)


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


def test_ac_qveris_direct_execution_verifies_a_frozen_tool_absent_from_ranking(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.url.path == "/api/v1/search":
                return httpx.Response(
                    200, json={"search_id": "search-123", "results": []}
                )
            if request.url.path == "/api/v1/tools/by-ids":
                return httpx.Response(
                    200, json={"results": [{"tool_id": "frozen-tool"}]}
                )
            return httpx.Response(200, json={"result": {"data": []}})

        client = QverisToolClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            _store(tmp_path),
            "controlled-key",
        )
        try:
            execution = await execute_discovered_tool(
                client,
                "search",
                "ETF holdings",
                "frozen-tool",
                {"symbol": "SPY"},
            )
        finally:
            await client.close()

        assert execution.result.raw_path.exists()
        assert [request.url.path for request in calls] == [
            "/api/v1/search",
            "/api/v1/tools/by-ids",
            "/api/v1/tools/execute",
        ]

    asyncio.run(run())


def test_ac_qveris_direct_execution_rejects_a_tool_absent_from_exact_lookup(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.url.path == "/api/v1/search":
                return httpx.Response(
                    200, json={"search_id": "search-123", "results": []}
                )
            return httpx.Response(200, json={"results": []})

        client = QverisToolClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            _store(tmp_path),
            "controlled-key",
        )
        try:
            with pytest.raises(QverisProtocolError, match="exact tool lookup"):
                await execute_discovered_tool(
                    client,
                    "search",
                    "ETF holdings",
                    "missing-tool",
                    {"symbol": "SPY"},
                )
        finally:
            await client.close()

        assert len(calls) == 2

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
        "keys": ["data"],
        "field_count": 2,
        "fields": {
            "data": {
                "type": "object",
                "keys": ["holdings", "symbol"],
                "field_count": 2,
                "fields": {
                    "holdings": {"type": "array", "length": 1},
                    "symbol": {"type": "string"},
                },
            }
        },
    }
    assert "SPY" not in repr(shape)
    assert "AAPL" not in repr(shape)
    assert "private-request-id" not in repr(shape)


def test_ac_qveris_response_shape_redacts_dynamic_object_keys() -> None:
    shape = public_response_shape({"data": {"holdings": {"AAPL": 0.07}}})

    assert shape["fields"] == {
        "data": {
            "type": "object",
            "keys": ["holdings"],
            "field_count": 1,
            "fields": {"holdings": {"type": "object", "keys": [], "field_count": 1}},
        }
    }
    assert "AAPL" not in repr(shape)


def test_ac_qveris_response_shape_can_expose_nested_structural_fields() -> None:
    shape = public_response_shape(
        {"result": {"data": {"holdings": [{"ticker": "AAPL"}]}}}, depth=4
    )

    assert shape["fields"]["result"]["fields"]["data"]["fields"]["holdings"] == {
        "type": "array",
        "length": 1,
        "item_shape": {"type": "object", "keys": ["ticker"], "field_count": 1},
    }
    assert "AAPL" not in repr(shape)


def test_ac_qveris_response_shape_allows_documented_finnhub_quote_keys() -> None:
    shape = public_response_shape(
        {"result": {"data": {"c": 201.0, "t": 1_700_000_000}}}, depth=4
    )

    assert shape["fields"]["result"]["fields"]["data"] == {
        "type": "object",
        "keys": ["c", "t"],
        "field_count": 2,
        "fields": {"c": {"type": "number"}, "t": {"type": "number"}},
    }
    assert "201.0" not in repr(shape)
    assert "1700000000" not in repr(shape)


def test_ac_qveris_response_shape_exposes_only_allowlisted_error_structure() -> None:
    shape = public_response_shape(
        {
            "result": {
                "data": {},
                "error_code": "invalid_symbol",
                "error_message": "NOTANETF is not a valid symbol",
                "request_id": "private-request-id",
            }
        },
        depth=3,
    )

    assert shape["fields"]["result"] == {
        "type": "object",
        "keys": ["data", "error_code", "error_message"],
        "field_count": 4,
        "fields": {
            "data": {"type": "object", "keys": [], "field_count": 0, "fields": {}},
            "error_code": {"type": "string"},
            "error_message": {"type": "string"},
        },
    }
    assert "invalid_symbol" not in repr(shape)
    assert "NOTANETF" not in repr(shape)
    assert "private-request-id" not in repr(shape)


def test_ac_qveris_response_shape_exposes_mcp_structure_without_values() -> None:
    shape = public_response_shape(
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "code": 1,
                            "msg": "success",
                            "data": json.dumps(
                                {
                                    "rows": [
                                        {
                                            "symbol": "600519.SH",
                                            "amount": 28.02,
                                        }
                                    ]
                                }
                            ),
                        }
                    ),
                }
            ],
            "is_error": False,
        },
        depth=8,
    )

    rendered = repr(shape)
    assert "content" in rendered
    assert "rows" in rendered
    assert "symbol" in rendered
    assert "600519.SH" not in rendered
    assert "28.02" not in rendered
