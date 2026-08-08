from __future__ import annotations

from pydantic import Field

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
    run_key: str = Field(min_length=1)
    raw_digest: EvidenceRef
    public_digest: EvidenceRef | None = None
    redaction_status: RedactionStatus
    disclosure_level: DisclosureLevel
    license_status: LicenseStatus
    extractor_version: SemanticVersion
    suite_fingerprint: Sha256
    # QVeris 网关侧观测；不代表供应商原生 API 延迟或定价
    latency_ms: float | None = None
    cost_credits: float | None = None
