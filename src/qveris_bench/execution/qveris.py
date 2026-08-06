from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.base import AdapterResult
from qveris_bench.execution.http import HttpAdapter
from qveris_bench.execution.request import TransportRequest

DEFAULT_QVERIS_API_BASE_URL = "https://qveris.ai/api/v1"


class QverisProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class QverisSearch:
    search_id: str
    result: AdapterResult


class QverisToolClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        store: RawArtifactStore,
        api_key: str,
        base_url: str = DEFAULT_QVERIS_API_BASE_URL,
    ) -> None:
        self._adapter = HttpAdapter(client, store)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def search(
        self, artifact_id: str, query: str, limit: int = 10
    ) -> QverisSearch:
        result = await self._adapter.invoke(
            artifact_id,
            TransportRequest(
                method="POST",
                url=f"{self._base_url}/search",
                bearer_token=self._api_key,
                json_body={"query": query, "limit": limit},
            ),
        )
        document = _document(result)
        search_id = document.get("search_id")
        if not isinstance(search_id, str) or not search_id:
            raise QverisProtocolError("QVeris search response is missing search_id")
        return QverisSearch(search_id, result)

    async def execute(
        self,
        artifact_id: str,
        tool_id: str,
        search_id: str,
        parameters: dict[str, object],
        max_response_size: int = 65536,
    ) -> AdapterResult:
        if not tool_id or not search_id:
            raise QverisProtocolError("tool_id and search_id are required")
        return await self._adapter.invoke(
            artifact_id,
            TransportRequest(
                method="POST",
                url=f"{self._base_url}/tools/execute",
                query={"tool_id": tool_id},
                bearer_token=self._api_key,
                json_body={
                    "search_id": search_id,
                    "parameters": parameters,
                    "max_response_size": max_response_size,
                },
            ),
        )

    async def close(self) -> None:
        await self._adapter.close()


def _document(result: AdapterResult) -> dict[str, Any]:
    try:
        document = json.loads(result.raw_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QverisProtocolError("QVeris response is not JSON") from exc
    if not isinstance(document, dict):
        raise QverisProtocolError("QVeris response must be an object")
    return document
