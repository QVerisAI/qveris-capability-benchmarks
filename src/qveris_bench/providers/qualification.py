from __future__ import annotations

from typing import Protocol

from qveris_bench.models.provider import QualificationDecision


class QualifiedAccessPath(Protocol):
    @property
    def access_path_id(self) -> str: ...

    @property
    def qualification(self) -> QualificationDecision | None: ...


class CohortValidationError(ValueError):
    pass


def check_frozen_cohort(
    access_paths: tuple[QualifiedAccessPath, ...],
) -> None:
    unqualified = [
        access_path.access_path_id
        for access_path in access_paths
        if access_path.qualification is None
    ]
    if unqualified:
        raise CohortValidationError(
            "Access Paths missing terminal qualification: " + ", ".join(unqualified)
        )
