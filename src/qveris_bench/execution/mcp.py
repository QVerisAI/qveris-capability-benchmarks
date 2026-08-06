from __future__ import annotations

import json
from typing import Protocol

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.base import AdapterResult
from qveris_bench.execution.errors import TransportError
from qveris_bench.execution.request import TransportRequest


class McpSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, object]) -> object: ...


class McpAdapter:
    def __init__(
        self, session: McpSession, canonical_tool: str, store: RawArtifactStore
    ) -> None:
        self._session = session
        self._canonical_tool = canonical_tool
        self._store = store

    async def invoke(
        self,
        artifact_id: str,
        arguments: dict[str, object],
        tool_name: str | None = None,
    ) -> AdapterResult:
        tool = tool_name or self._canonical_tool
        if tool != self._canonical_tool:
            raise TransportError(
                "canonical_tool_required", "only the frozen canonical tool may run"
            )
        try:
            result = await self._session.call_tool(tool, arguments)
        except Exception as exc:
            raise TransportError(
                "mcp_error", "canonical tool invocation failed"
            ) from exc
        payload = json.dumps(result, default=str, sort_keys=True).encode()
        request = TransportRequest(method="MCP", url=f"mcp://tool/{tool}")
        return AdapterResult.from_payload(
            request, 200, {}, payload, self._store, artifact_id
        )
