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
        if _is_structured_error(result):
            payload = json.dumps(result, default=str, sort_keys=True).encode()
            record = self._store.persist(artifact_id, payload)
            raise TransportError(
                "mcp_tool_error", "canonical tool returned an error", record.digest
            )
        payload = json.dumps(result, default=str, sort_keys=True).encode()
        request = TransportRequest(method="MCP", url=f"mcp://tool/{tool}")
        return AdapterResult.from_payload(
            request, 200, {}, payload, self._store, artifact_id
        )

    async def close(self) -> None:
        close = getattr(self._session, "aclose", None)
        if close is not None:
            await close()


def _is_structured_error(result: object) -> bool:
    if isinstance(result, dict):
        return bool(result.get("isError") or result.get("is_error"))
    return bool(getattr(result, "isError", False) or getattr(result, "is_error", False))
