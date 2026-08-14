from __future__ import annotations

from qveris_bench.execution.base import AdapterResult


class TransportError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        evidence_digest: str | None = None,
        result: AdapterResult | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.evidence_digest = evidence_digest
        self.result = result
