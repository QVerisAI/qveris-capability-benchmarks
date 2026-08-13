from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId

SectionName = Annotated[
    str,
    Field(pattern=r"^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$", max_length=128),
]


class PublicationPackageSpec(FrozenModel):
    package_id: StableId
    adapter_id: StableId
    adapter_version: SemanticVersion
    cap_id: StableId
    release_sections: tuple[SectionName, ...] = Field(min_length=1)
    adapter_sources: tuple[str, ...] = Field(min_length=1)
    adapter_digest: EvidenceRef

    @model_validator(mode="after")
    def release_sections_are_unique(self) -> PublicationPackageSpec:
        if len(set(self.release_sections)) != len(self.release_sections):
            raise ValueError("publication release sections must be unique")
        return self


class PublicationPackageManifest(FrozenModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    schema_version: Literal[1]
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
