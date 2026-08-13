from __future__ import annotations

from typing import Annotated

from pydantic import Field, HttpUrl, model_validator

from qveris_bench.models.base import FrozenModel, SemanticVersion, Sha256, StableId
from qveris_bench.models.enums import SourceType

HarborCapabilityId = Annotated[
    str,
    Field(pattern=r"^[A-Z][A-Z0-9]*(?:\.[A-Z][A-Z0-9_]*)+$", min_length=3),
]


class SourceReference(FrozenModel):
    source_type: SourceType
    harbor_capability_id: HarborCapabilityId
    contract_version: int = Field(ge=1)
    catalog_snapshot_digest: Sha256
    contract_digest: Sha256

    @model_validator(mode="after")
    def require_source_provenance(self) -> SourceReference:
        if self.source_type is not SourceType.HARBOR_CATALOG:
            raise ValueError("formal CAP source must be the Harbor catalog")
        return self


class CapDefinition(FrozenModel):
    cap_id: StableId
    version: SemanticVersion
    name: str = Field(min_length=1)
    business_use: str = Field(min_length=10)
    scope: tuple[str, ...] = Field(min_length=1)
    exclusions: tuple[str, ...] = ()
    markets: tuple[str, ...] = ()
    asset_types: tuple[str, ...] = ()
    sources: tuple[SourceReference, ...] = Field(min_length=1)
