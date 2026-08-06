from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.qveris import QverisToolClient


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
