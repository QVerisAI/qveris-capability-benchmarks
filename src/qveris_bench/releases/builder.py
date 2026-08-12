from __future__ import annotations

from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.releases.canonical import canonical_release_bytes
from qveris_bench.releases.gate import validate_release_inputs


def build_release(
    release: BenchmarkRelease,
    cells: tuple[RunCell, ...],
    evidence: tuple[EvidenceBundle, ...],
    *,
    require_attribution: bool = True,
) -> bytes:
    validate_release_inputs(
        release, cells, evidence, require_attribution=require_attribution
    )
    payload = {
        "release": release.model_dump(mode="json", exclude_none=True),
        "cells": [
            # 归因仅在已记录时序列化，保证历史 release 字节级可重建
            cell.model_dump(
                mode="json",
                exclude={"failure_attribution"}
                if cell.failure_attribution is None
                else set(),
            )
            for cell in sorted(cells, key=lambda item: item.run_key)
        ],
        "evidence": [
            bundle.model_dump(mode="json", exclude_none=True)
            for bundle in sorted(evidence, key=lambda item: item.evidence_id)
        ],
    }
    return canonical_release_bytes(payload)
