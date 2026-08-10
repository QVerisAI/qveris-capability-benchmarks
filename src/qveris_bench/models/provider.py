from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, HttpUrl

from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    Sha256,
    StableId,
)
from qveris_bench.models.enums import (
    AccessPathType,
    AccessProtocol,
    DisclosureLevel,
    LicenseStatus,
    QualificationDisposition,
)

CurrencyCode = Annotated[str, Field(pattern=r"^(?:[A-Z]{3}|NONE)$")]


class OfficialPricingFact(FrozenModel):
    pricing_id: StableId
    pricing_url: HttpUrl
    applies_to: Literal["provider_wide"] | tuple[StableId, ...]
    currencies: tuple[CurrencyCode, ...] = Field(min_length=1)
    free_tier: str = Field(min_length=1)
    paid_plans: str = Field(min_length=1)
    verified_at: date
    source_digest: Sha256
    extractor_version: SemanticVersion
    suite_fingerprint: Sha256
    disclosure_level: DisclosureLevel
    license_status: LicenseStatus


class ProviderProfile(FrozenModel):
    provider_id: StableId
    official_name: str = Field(min_length=1)
    website: HttpUrl
    market_coverage: tuple[str, ...] = ()
    official_pricing: tuple[OfficialPricingFact, ...] = Field(min_length=1)


class QualificationDecision(FrozenModel):
    disposition: QualificationDisposition
    reason: str = Field(min_length=10)
    evidence_digest: EvidenceRef


class AccessPath(FrozenModel):
    access_path_id: StableId
    provider_id: StableId
    path_type: AccessPathType
    official_source: HttpUrl
    plan_name: str | None = None
    authorization: str = Field(min_length=1)
    canonical_interface: str = Field(min_length=1)
    protocol: AccessProtocol
    endpoint_url: HttpUrl | None
    authentication: str = Field(min_length=1)
    agent_trial_eligible: bool
    qualification: QualificationDecision | None = None
