from __future__ import annotations

from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    Sha256,
    StableId,
)
from qveris_bench.models.enums import DisclosureLevel, LicenseStatus, RedactionStatus


class EvidenceBundle(FrozenModel):
    evidence_id: StableId
    raw_digest: EvidenceRef
    public_digest: EvidenceRef | None = None
    redaction_status: RedactionStatus
    disclosure_level: DisclosureLevel
    license_status: LicenseStatus
    extractor_version: SemanticVersion
    suite_fingerprint: Sha256
