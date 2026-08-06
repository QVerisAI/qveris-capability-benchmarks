from __future__ import annotations

from typing import Annotated

from pydantic import Field, HttpUrl, model_validator

from qveris_bench.models.base import FrozenModel, SemanticVersion, StableId
from qveris_bench.models.enums import SourceType

CommitRef = Annotated[str, Field(pattern=r"^[0-9a-f]{7,64}$")]


class SourceReference(FrozenModel):
    source_type: SourceType
    repository: HttpUrl | None = None
    commit: CommitRef | None = None
    task_id: str | None = Field(default=None, min_length=1)
    internal_reference: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_source_provenance(self) -> SourceReference:
        if self.source_type is SourceType.EXTERNAL_REPOSITORY:
            missing = [
                name
                for name in ("repository", "commit", "task_id")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError("external source requires " + ", ".join(missing))
        if (
            self.source_type is SourceType.CUSTOMER_QUESTION
            and not self.internal_reference
        ):
            raise ValueError("customer source requires internal_reference")
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
