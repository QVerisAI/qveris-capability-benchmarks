from __future__ import annotations

import httpx

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.base import AdapterResult
from qveris_bench.execution.errors import TransportError
from qveris_bench.execution.request import TransportRequest


class HttpAdapter:
    def __init__(self, client: httpx.AsyncClient, store: RawArtifactStore) -> None:
        self._client = client
        self._store = store

    async def invoke(
        self, artifact_id: str, request: TransportRequest
    ) -> AdapterResult:
        headers = dict(request.headers)
        if request.bearer_token:
            headers["Authorization"] = f"Bearer {request.bearer_token}"
        try:
            response = await self._client.request(
                request.method,
                request.url,
                headers=headers,
                params=request.query,
                json=request.json_body,
                timeout=request.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise TransportError("timeout", "provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise TransportError("network_error", "provider transport failed") from exc
        result = AdapterResult.from_payload(
            request,
            response.status_code,
            dict(response.headers),
            response.content,
            self._store,
            artifact_id,
        )
        if response.status_code == 429:
            raise TransportError(
                "rate_limited", "provider rate limit", result.raw_digest
            )
        if response.status_code >= 400:
            raise TransportError(
                "http_error",
                f"provider returned {response.status_code}",
                result.raw_digest,
            )
        return result

    async def close(self) -> None:
        await self._client.aclose()
