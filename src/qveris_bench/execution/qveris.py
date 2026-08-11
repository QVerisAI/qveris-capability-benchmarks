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
_PUBLIC_RESPONSE_KEYS = frozenset(
    {
        "code",
        "composition",
        "content",
        "c",
        "data",
        "d",
        "dp",
        "error",
        "error_code",
        "error_message",
        "holdings",
        "h",
        "is_error",
        "l",
        "message",
        "meta",
        "msg",
        "o",
        "pc",
        "records",
        "result",
        "result_type",
        "results",
        "rows",
        "status",
        "subCode",
        "subMsg",
        "symbol",
        "table",
        "tables",
        "text",
        "ticker",
        "t",
        "weight",
        "weights",
    }
)


class QverisProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class QverisSearch:
    search_id: str
    result: AdapterResult


@dataclass(frozen=True)
class QverisDirectExecution:
    search: QverisSearch
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

    async def describe_tools(
        self, artifact_id: str, tool_ids: tuple[str, ...]
    ) -> AdapterResult:
        if not tool_ids or any(not tool_id for tool_id in tool_ids):
            raise QverisProtocolError("at least one tool_id is required")
        return await self._adapter.invoke(
            artifact_id,
            TransportRequest(
                method="POST",
                url=f"{self._base_url}/tools/by-ids",
                bearer_token=self._api_key,
                json_body={"tool_ids": list(tool_ids)},
            ),
        )

    async def close(self) -> None:
        await self._adapter.close()


async def execute_discovered_tool(
    client: QverisToolClient,
    search_artifact_id: str,
    query: str,
    tool_id: str,
    parameters: dict[str, object],
) -> QverisDirectExecution:
    search = await client.search(search_artifact_id, query)
    document = _document(search.result)
    results = document.get("results", [])
    discovered_ids = {
        item.get("tool_id")
        for item in results
        if isinstance(item, dict) and isinstance(item.get("tool_id"), str)
    }
    if tool_id not in discovered_ids:
        description = await client.describe_tools(
            f"{search_artifact_id}-describe", (tool_id,)
        )
        described_ids = _tool_ids(_document(description))
        if tool_id not in described_ids:
            raise QverisProtocolError("tool_id was not returned by exact tool lookup")
    result = await client.execute(
        f"{search_artifact_id}-execute", tool_id, search.search_id, parameters
    )
    return QverisDirectExecution(search=search, result=result)


def _tool_ids(document: dict[str, Any]) -> set[str]:
    for key in ("results", "tools"):
        values = document.get(key)
        if isinstance(values, list):
            return {
                item["tool_id"]
                for item in values
                if isinstance(item, dict) and isinstance(item.get("tool_id"), str)
            }
    return set()


def _document(result: AdapterResult) -> dict[str, Any]:
    try:
        document = json.loads(result.raw_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QverisProtocolError("QVeris response is not JSON") from exc
    if not isinstance(document, dict):
        raise QverisProtocolError("QVeris response must be an object")
    return document


def gateway_metrics(document: dict[str, Any]) -> tuple[float | None, float | None]:
    """从 QVeris API 响应提取网关侧延迟与费用观测。"""
    latency_ms = _finite_float(document.get("elapsed_time_ms"))
    cost_credits = _finite_float(document.get("cost"))
    return latency_ms, cost_credits


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if numeric <= 0:
        return None
    return numeric


def public_response_shape(value: object, depth: int = 2) -> dict[str, object]:
    if isinstance(value, dict):
        keys = sorted(
            key
            for key in value
            if isinstance(key, str) and key in _PUBLIC_RESPONSE_KEYS
        )
        shape: dict[str, object] = {
            "type": "object",
            "keys": keys,
            "field_count": len(value),
        }
        if depth > 0:
            shape["fields"] = {
                key: public_response_shape(value[key], depth - 1) for key in keys
            }
        return shape
    if isinstance(value, list):
        array_shape: dict[str, object] = {"type": "array", "length": len(value)}
        if value and depth > 0:
            array_shape["item_shape"] = public_response_shape(value[0], depth - 1)
        return array_shape
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, (int, float)):
        return {"type": "number"}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {"type": "string"}
        if isinstance(decoded, (dict, list)):
            return {
                "type": "json_string",
                "value_shape": public_response_shape(decoded, depth),
            }
        return {"type": "string"}
    return {"type": type(value).__name__}
