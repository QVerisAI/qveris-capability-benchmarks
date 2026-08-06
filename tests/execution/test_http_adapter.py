import asyncio
from pathlib import Path

import httpx
import pytest

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.errors import TransportError
from qveris_bench.execution.http import HttpAdapter
from qveris_bench.execution.request import TransportRequest


def _store(tmp_path: Path) -> RawArtifactStore:
    return RawArtifactStore(tmp_path / "raw", tmp_path / "repo")


def test_ac2_http_adapter_places_bearer_auth_and_persists_response(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer token-value"
            assert request.url.params["symbol"] == "AAPL"
            return httpx.Response(
                200, json={"price": 10}, headers={"x-request-id": "r-1"}
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = HttpAdapter(client, _store(tmp_path))
        result = await adapter.invoke(
            "cell-1",
            TransportRequest(
                method="GET",
                url="https://provider.test/quote",
                query={"symbol": "AAPL"},
                bearer_token="token-value",
            ),
        )
        assert result.status_code == 200
        assert b"price" in result.raw_path.read_bytes()
        await adapter.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("status", "error_code"), [(429, "rate_limited"), (500, "http_error")]
)
def test_ac2_http_adapter_normalizes_failure_statuses(
    tmp_path: Path, status: int, error_code: str
) -> None:
    async def run() -> None:
        adapter = HttpAdapter(
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(status))
            ),
            _store(tmp_path),
        )
        with pytest.raises(TransportError, match=error_code) as error:
            await adapter.invoke(
                "cell-1", TransportRequest(method="GET", url="https://provider.test")
            )
        assert error.value.evidence_digest is not None
        await adapter.close()

    asyncio.run(run())
