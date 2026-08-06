import asyncio
from pathlib import Path

import pytest

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.errors import TransportError
from qveris_bench.execution.mcp import McpAdapter


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text": "ok"}]}


def test_ac3_mcp_run_invokes_only_frozen_canonical_tool(tmp_path: Path) -> None:
    async def run() -> None:
        session = FakeSession()
        store = RawArtifactStore(tmp_path / "raw", tmp_path / "repo")
        adapter = McpAdapter(session, "get-quote", store)
        result = await adapter.invoke("cell-1", {"symbol": "AAPL"})
        assert result.status_code == 200
        assert session.calls == [("get-quote", {"symbol": "AAPL"})]

    asyncio.run(run())


def test_ac3_mcp_run_rejects_noncanonical_tool(tmp_path: Path) -> None:
    async def run() -> None:
        store = RawArtifactStore(tmp_path / "raw", tmp_path / "repo")
        adapter = McpAdapter(FakeSession(), "get-quote", store)
        with pytest.raises(TransportError, match="canonical"):
            await adapter.invoke("cell-1", {}, tool_name="search-tools")

    asyncio.run(run())


def test_ac3_mcp_structured_error_persists_evidence(tmp_path: Path) -> None:
    async def run() -> None:
        session = FakeSession()

        async def error(_: str, __: dict[str, object]) -> object:
            return {"isError": True, "content": []}

        session.call_tool = error  # type: ignore[method-assign]
        store = RawArtifactStore(tmp_path / "raw", tmp_path / "repo")
        adapter = McpAdapter(session, "get-quote", store)
        with pytest.raises(TransportError, match="mcp_tool_error") as error_info:
            await adapter.invoke("cell-1", {})
        assert error_info.value.evidence_digest is not None

    asyncio.run(run())
