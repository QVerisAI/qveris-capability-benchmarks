from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from qveris_bench.evidence.policy import validate_publication
from qveris_bench.models.evidence import EvidenceBundle


@dataclass(frozen=True)
class EvidenceIndexEntry:
    evidence_id: str
    raw_digest: str
    public_digest: str
    extractor_version: str
    suite_fingerprint: str
    disclosure_level: str
    license_status: str

    @classmethod
    def from_bundle(cls, bundle: EvidenceBundle) -> EvidenceIndexEntry:
        validate_publication(bundle)
        if bundle.public_digest is None:
            raise ValueError("an evidence index entry requires a public digest")
        return cls(
            evidence_id=bundle.evidence_id,
            raw_digest=bundle.raw_digest,
            public_digest=bundle.public_digest,
            extractor_version=bundle.extractor_version,
            suite_fingerprint=bundle.suite_fingerprint,
            disclosure_level=bundle.disclosure_level,
            license_status=bundle.license_status,
        )


@dataclass(frozen=True)
class EvidenceIndex:
    entries: tuple[EvidenceIndexEntry, ...]

    def render(self) -> bytes:
        ordered_entries = sorted(self.entries, key=lambda item: item.evidence_id)
        payload = {"entries": [asdict(entry) for entry in ordered_entries]}
        return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()

    def write(self, path: Path) -> bytes:
        content = self.render()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return content
