from __future__ import annotations

import pytest

from qveris_bench.models.cap import SourceReference
from qveris_bench.models.enums import (
    CellState,
    DimensionState,
    DisclosureLevel,
    LicenseStatus,
    RedactionStatus,
    ReleaseFactType,
    SourceType,
)
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.metric import (
    MetricDefinition,
    metric_definition_digest,
    metric_ranking_cohort_digest,
)
from qveris_bench.models.release import BenchmarkRelease, ReleaseFact
from qveris_bench.models.run import RunCell
from qveris_bench.releases.gate import ReleaseGateError, validate_release_inputs

SUITE_FINGERPRINT = "c" * 64
METHOD_DIGEST = "sha256:" + "d" * 64
COHORT_DIGEST = "sha256:" + "e" * 64


def _harbor_source() -> SourceReference:
    return SourceReference(
        source_type=SourceType.HARBOR_CATALOG,
        harbor_capability_id="MKT.L1.RT",
        contract_version=1,
        catalog_snapshot_digest="a" * 64,
        contract_digest="b" * 64,
    )


def _definition() -> MetricDefinition:
    return MetricDefinition(
        definition_id="stock-quote-error-recoverability",
        cap_id="stock-quote",
        cap_version="2.0.0",
        metric_id="error-recoverability",
        dimension_id="agent-interface-error-recoverability",
        method_version="1.0.0",
        method_digest=METHOD_DIGEST,
        scale_min=0,
        scale_max=100,
        unit="points",
        direction="higher_is_better",
    )


def _cell(index: int) -> RunCell:
    return RunCell(
        run_key=f"cell-{index}",
        case_id="case-1",
        provider_id=f"provider-{index}",
        access_path_id=f"path-{index}",
        mode="direct",
        round=1,
        state=CellState.COMPLETED,
    )


def _evidence(index: int) -> EvidenceBundle:
    return EvidenceBundle(
        evidence_id=f"evidence-{index}",
        run_key=f"cell-{index}",
        raw_digest="sha256:" + str(index) * 64,
        public_digest="sha256:" + chr(96 + index) * 64,
        redaction_status=RedactionStatus.SANITIZED,
        disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
        license_status=LicenseStatus.CLEARED,
        extractor_version="1.0.0",
        suite_fingerprint=SUITE_FINGERPRINT,
    )


def _fact(
    index: int, *, rank_of: int = 2, suite: str = SUITE_FINGERPRINT
) -> ReleaseFact:
    evidence_ref = "sha256:" + chr(96 + index) * 64
    common = {
        "metric_id": "error-recoverability",
        "definition_digest": metric_definition_digest(_definition()),
        "dimension_id": "agent-interface-error-recoverability",
        "cap_id": "stock-quote",
        "cap_version": "2.0.0",
        "provider_id": f"provider-{index}",
        "access_path_id": f"path-{index}",
        "method_version": "1.0.0",
        "method_digest": METHOD_DIGEST,
        "suite_fingerprint": suite,
        "evidence_refs": [evidence_ref],
        "scale_min": 0,
        "scale_max": 100,
        "unit": "points",
        "direction": "higher_is_better",
    }
    return ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.MEASURED,
        dimension_id="agent-interface-error-recoverability",
        metric_score=common | {"value": 90 - index},
        metric_ranking=common
        | {
            "cohort_id": "stock-quote-v3-cohort",
            "cohort_digest": COHORT_DIGEST,
            "rank": index,
            "rank_of": rank_of,
            "tie_method": "competition",
        },
        evidence_refs=(evidence_ref,),
    )


def _release(*facts: ReleaseFact) -> BenchmarkRelease:
    rankings = [
        fact.metric_ranking for fact in facts if fact.metric_ranking is not None
    ]
    cohort_digest = metric_ranking_cohort_digest(rankings) if rankings else None
    cohort_size = max((ranking.rank_of for ranking in rankings), default=len(facts))
    normalized_facts = tuple(
        fact.model_copy(
            update={
                "metric_ranking": fact.metric_ranking.model_copy(
                    update={"cohort_digest": cohort_digest}
                )
            }
        )
        if fact.metric_ranking is not None
        else fact
        for fact in facts
    )
    return BenchmarkRelease(
        release_id="metric-release",
        version="1.0.0",
        suite_fingerprint=SUITE_FINGERPRINT,
        run_plan_digest="sha256:" + "f" * 64,
        evidence_ids=tuple(f"evidence-{index}" for index in range(1, cohort_size + 1)),
        cap_id="stock-quote",
        cap_version="2.0.0",
        cap_sources=(_harbor_source(),),
        metric_definitions=(_definition(),),
        developer_selection_facts=normalized_facts,
    )


def test_ac2_release_gate_accepts_complete_frozen_metric_cohort() -> None:
    validate_release_inputs(
        _release(_fact(1), _fact(2)),
        (_cell(1), _cell(2)),
        (_evidence(1), _evidence(2)),
        metric_registry=(_definition(),),
    )


def test_ac2_release_gate_rejects_incomplete_ranking_cohort() -> None:
    with pytest.raises(ReleaseGateError, match="complete frozen cohort"):
        validate_release_inputs(
            _release(_fact(1)),
            (_cell(1), _cell(2)),
            (_evidence(1), _evidence(2)),
            metric_registry=(_definition(),),
        )


def test_ac2_release_gate_rejects_metric_suite_mismatch() -> None:
    with pytest.raises(ReleaseGateError, match="suite fingerprint"):
        validate_release_inputs(
            _release(_fact(1, suite="9" * 64), _fact(2)),
            (_cell(1), _cell(2)),
            (_evidence(1), _evidence(2)),
            metric_registry=(_definition(),),
        )


def test_ac2_release_gate_rejects_evidence_from_another_provider_cell() -> None:
    first = _fact(1)
    wrong_reference = "sha256:" + "b" * 64
    mismatched = first.model_copy(
        update={
            "evidence_refs": (wrong_reference,),
            "metric_score": first.metric_score.model_copy(
                update={"evidence_refs": (wrong_reference,)}
            ),
            "metric_ranking": first.metric_ranking.model_copy(
                update={"evidence_refs": (wrong_reference,)}
            ),
        }
    )

    with pytest.raises(ReleaseGateError, match="Provider / Access Path"):
        validate_release_inputs(
            _release(mismatched, _fact(2)),
            (_cell(1), _cell(2)),
            (_evidence(1), _evidence(2)),
            metric_registry=(_definition(),),
        )


def test_ac2_release_gate_rejects_inconsistent_frozen_cohort() -> None:
    second = _fact(2)
    changed_digest = "sha256:" + "9" * 64
    inconsistent = second.model_copy(
        update={
            "metric_score": second.metric_score.model_copy(
                update={"method_digest": changed_digest}
            ),
            "metric_ranking": second.metric_ranking.model_copy(
                update={"method_digest": changed_digest}
            ),
        }
    )

    with pytest.raises(ReleaseGateError, match="registered CAP definition"):
        validate_release_inputs(
            _release(_fact(1), inconsistent),
            (_cell(1), _cell(2)),
            (_evidence(1), _evidence(2)),
            metric_registry=(_definition(),),
        )


def test_ac2_release_gate_rejects_forged_cohort_digest() -> None:
    release = _release(_fact(1), _fact(2))
    first = release.developer_selection_facts[0]
    forged = first.model_copy(
        update={
            "metric_ranking": first.metric_ranking.model_copy(
                update={"cohort_digest": "sha256:" + "7" * 64}
            )
        }
    )
    forged_release = release.model_copy(
        update={
            "developer_selection_facts": (
                forged,
                release.developer_selection_facts[1],
            )
        }
    )

    with pytest.raises(ReleaseGateError, match="cohort digest mismatch"):
        validate_release_inputs(
            forged_release,
            (_cell(1), _cell(2)),
            (_evidence(1), _evidence(2)),
            metric_registry=(_definition(),),
        )


def test_ac3_release_gate_rejects_unregistered_metric_definition() -> None:
    release = _release(_fact(1), _fact(2))
    first = release.developer_selection_facts[0]
    unregistered = first.model_copy(
        update={
            "metric_score": first.metric_score.model_copy(
                update={"definition_digest": "sha256:" + "8" * 64}
            )
        }
    )

    with pytest.raises(ReleaseGateError, match="registered CAP metric definition"):
        validate_release_inputs(
            release.model_copy(
                update={
                    "developer_selection_facts": (
                        unregistered,
                        release.developer_selection_facts[1],
                    )
                }
            ),
            (_cell(1), _cell(2)),
            (_evidence(1), _evidence(2)),
            metric_registry=(_definition(),),
        )


def test_ac3_release_gate_rejects_self_attested_metric_registry() -> None:
    with pytest.raises(ReleaseGateError, match="CAP-owned metric registry"):
        validate_release_inputs(
            _release(_fact(1), _fact(2)),
            (_cell(1), _cell(2)),
            (_evidence(1), _evidence(2)),
        )


def test_ac2_release_gate_rejects_rank_reversed_against_scores() -> None:
    release = _release(_fact(1), _fact(2))
    first, second = release.developer_selection_facts
    reversed_release = release.model_copy(
        update={
            "developer_selection_facts": (
                first.model_copy(
                    update={
                        "metric_score": first.metric_score.model_copy(
                            update={"value": 10}
                        )
                    }
                ),
                second.model_copy(
                    update={
                        "metric_score": second.metric_score.model_copy(
                            update={"value": 90}
                        )
                    }
                ),
            )
        }
    )

    with pytest.raises(ReleaseGateError, match="score ordering"):
        validate_release_inputs(
            reversed_release,
            (_cell(1), _cell(2)),
            (_evidence(1), _evidence(2)),
            metric_registry=(_definition(),),
        )


@pytest.mark.parametrize(
    ("tie_method", "ranks", "message"),
    (
        ("dense", (1, 3, 3), "dense"),
        ("competition", (1, 1, 2), "competition"),
    ),
)
def test_ac2_release_gate_rejects_invalid_tie_sequences(
    tie_method: str, ranks: tuple[int, ...], message: str
) -> None:
    facts = tuple(
        _fact(index, rank_of=3).model_copy(
            update={
                "metric_ranking": _fact(index, rank_of=3).metric_ranking.model_copy(
                    update={"tie_method": tie_method, "rank": rank}
                )
            }
        )
        for index, rank in enumerate(ranks, start=1)
    )

    with pytest.raises(ReleaseGateError, match=message):
        validate_release_inputs(
            _release(*facts),
            tuple(_cell(index) for index in range(1, 4)),
            tuple(_evidence(index) for index in range(1, 4)),
            metric_registry=(_definition(),),
        )
