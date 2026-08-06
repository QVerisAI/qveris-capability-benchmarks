from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import Field

from qveris_bench.models.base import EvidenceRef, FrozenModel


class QualificationDisposition(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


class QualificationDecision(FrozenModel):
    disposition: QualificationDisposition
    reason: str = Field(min_length=10)
    evidence_digest: EvidenceRef


class QualifiedProviderRecord(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def qualification(self) -> QualificationDecision | None: ...


class CohortValidationError(ValueError):
    pass


def check_frozen_cohort(
    records: tuple[QualifiedProviderRecord, ...],
) -> None:
    unqualified = [
        record.provider_id for record in records if record.qualification is None
    ]
    if unqualified:
        raise CohortValidationError(
            "providers missing terminal qualification: " + ", ".join(unqualified)
        )
