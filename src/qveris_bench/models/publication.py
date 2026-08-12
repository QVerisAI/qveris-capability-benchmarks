from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId

CapabilityId = Annotated[
    str,
    Field(pattern=r"^[A-Z][A-Z0-9]*(?:\.[A-Z0-9]+)+$", max_length=128),
]
SectionName = Annotated[
    str,
    Field(pattern=r"^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$", max_length=128),
]


class PublicationPackageSpec(FrozenModel):
    package_id: StableId
    adapter_id: StableId
    adapter_version: SemanticVersion
    cap_id: CapabilityId
    release_sections: tuple[SectionName, ...] = Field(min_length=1)


class PublicationPackageManifest(FrozenModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    schema_version: int = Field(ge=1)
    benchmark_id: StableId
    article_slug: StableId
    edition: date
    publication_package: PublicationPackageSpec


class PublicationReleaseRef(FrozenModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    directory: str = Field(min_length=1)
    digest: EvidenceRef


class PublicationReproductionReport(FrozenModel):
    package_id: StableId
    package_digest: EvidenceRef
    status: Literal["verified"]
    release_count: int = Field(ge=1)
    checks: tuple[SectionName, ...]
    canonical_chart_bytes_verified: bool
