from __future__ import annotations


class TransportError(RuntimeError):
    def __init__(
        self, code: str, message: str, evidence_digest: str | None = None
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.evidence_digest = evidence_digest
