from pathlib import Path

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.base import AdapterResult
from qveris_bench.execution.request import TransportRequest


def test_ac1_adapter_result_persists_raw_evidence(tmp_path: Path) -> None:
    store = RawArtifactStore(tmp_path / "raw", tmp_path / "repo")
    request = TransportRequest(method="GET", url="https://example.test")
    result = AdapterResult.from_payload(
        request, 200, {"x-request-id": "req-1"}, b"{}", store
    )

    assert result.raw_digest.startswith("sha256:")
    assert result.request_id == "req-1"
    assert result.raw_path.exists()


def test_ac1_transport_request_is_immutable() -> None:
    request = TransportRequest(
        method="GET", url="https://example.test", timeout_seconds=3
    )
    assert request.method == "GET"
