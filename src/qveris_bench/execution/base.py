from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.request import TransportRequest


@dataclass(frozen=True)
class AdapterResult:
    status_code: int
    headers: dict[str, str]
    request_id: str | None
    raw_digest: str
    raw_path: Path

    @classmethod
    def from_payload(
        cls,
        request: TransportRequest,
        status_code: int,
        headers: dict[str, str],
        payload: bytes,
        store: RawArtifactStore,
        artifact_id: str = "transport",
    ) -> AdapterResult:
        record = store.persist(artifact_id, payload)
        request_id = headers.get("x-request-id") or headers.get("request-id")
        return cls(status_code, headers, request_id, record.digest, record.path)
