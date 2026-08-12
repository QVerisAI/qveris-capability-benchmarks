from __future__ import annotations

from qveris_bench.evidence.policy import PublicationPolicyError, validate_publication
from qveris_bench.models.enums import CellState, DimensionState
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.metric import MetricRanking, MetricScore
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.outcomes.attribution import (
    AttributionError,
    ensure_provider_side_attribution,
)


class ReleaseGateError(ValueError):
    pass


_TERMINAL = {
    CellState.COMPLETED,
    CellState.PROVIDER_NEGATIVE,
    CellState.EXCLUDED,
    CellState.NOT_APPLICABLE,
}


def validate_release_inputs(
    release: BenchmarkRelease,
    cells: tuple[RunCell, ...],
    evidence: tuple[EvidenceBundle, ...],
    *,
    require_attribution: bool = True,
) -> None:
    open_cells = [cell.run_key for cell in cells if cell.state not in _TERMINAL]
    if open_cells:
        raise ReleaseGateError("open run cells: " + ", ".join(open_cells))
    if not evidence:
        raise ReleaseGateError("release requires evidence")
    evidence_ids = {bundle.evidence_id for bundle in evidence}
    if len(evidence_ids) != len(evidence):
        raise ReleaseGateError("duplicate evidence IDs")
    if set(release.evidence_ids) != evidence_ids:
        raise ReleaseGateError("release evidence IDs do not match evidence bundles")
    cell_run_keys = [cell.run_key for cell in cells]
    if len(set(cell_run_keys)) != len(cell_run_keys):
        raise ReleaseGateError("duplicate cell run keys")
    applicable_run_keys = [cell.run_key for cell in cells if cell.applicable]
    applicable_keys = set(applicable_run_keys)
    evidence_run_keys = [bundle.run_key for bundle in evidence]
    if len(set(evidence_run_keys)) != len(evidence_run_keys):
        raise ReleaseGateError("duplicate evidence run keys")
    if applicable_keys != set(evidence_run_keys):
        raise ReleaseGateError("applicable cells require matching evidence")
    for bundle in evidence:
        if bundle.suite_fingerprint != release.suite_fingerprint:
            raise ReleaseGateError("evidence suite fingerprint mismatch")
        try:
            validate_publication(bundle)
        except PublicationPolicyError as exc:
            raise ReleaseGateError("unsafe evidence") from exc
    available_digests = {
        digest
        for bundle in evidence
        for digest in (bundle.raw_digest, bundle.public_digest)
        if digest is not None
    }
    measured_refs = {
        str(reference)
        for fact in (
            release.developer_selection_facts
            + tuple(
                reference
                for feedback in release.provider_feedback_facts.values()
                for reference in feedback
            )
        )
        if fact.dimension_state == DimensionState.MEASURED
        for reference in fact.evidence_refs
    }
    missing_refs = measured_refs - available_digests
    if missing_refs:
        raise ReleaseGateError(
            "measured dimension facts reference missing evidence: "
            + ", ".join(sorted(missing_refs))
        )
    _validate_metrics(release, cells, evidence)
    if require_attribution:
        _validate_provider_negative_attribution(cells)


def _validate_metrics(
    release: BenchmarkRelease,
    cells: tuple[RunCell, ...],
    evidence: tuple[EvidenceBundle, ...],
) -> None:
    facts = release.developer_selection_facts + tuple(
        fact
        for provider_facts in release.provider_feedback_facts.values()
        for fact in provider_facts
    )
    metrics: tuple[MetricScore | MetricRanking, ...] = tuple(
        metric
        for fact in facts
        for metric in (fact.metric_score, fact.metric_ranking)
        if metric is not None
    )
    if any(metric.suite_fingerprint != release.suite_fingerprint for metric in metrics):
        raise ReleaseGateError("metric suite fingerprint mismatch")

    cells_by_run_key = {cell.run_key: cell for cell in cells}
    metric_scopes_by_digest: dict[str, set[tuple[str, str]]] = {}
    for bundle in evidence:
        cell = cells_by_run_key.get(bundle.run_key)
        if cell is None:
            continue
        scope = (str(cell.provider_id), str(cell.access_path_id))
        for digest in (bundle.raw_digest, bundle.public_digest):
            if digest is not None:
                metric_scopes_by_digest.setdefault(str(digest), set()).add(scope)
    for metric in metrics:
        metric_scope = (str(metric.provider_id), str(metric.access_path_id))
        if not any(
            metric_scope in metric_scopes_by_digest.get(str(reference), set())
            for reference in metric.evidence_refs
        ):
            raise ReleaseGateError(
                "metric evidence does not match its Provider / Access Path"
            )

    rankings_by_cohort: dict[str, list[MetricRanking]] = {}
    for metric in metrics:
        if isinstance(metric, MetricRanking):
            rankings_by_cohort.setdefault(str(metric.cohort_digest), []).append(metric)
    for rankings in rankings_by_cohort.values():
        _validate_ranking_cohort(rankings)


def _validate_ranking_cohort(rankings: list[MetricRanking]) -> None:
    first = rankings[0]
    signature = (
        first.cohort_id,
        first.metric_id,
        first.dimension_id,
        first.cap_id,
        first.cap_version,
        first.method_version,
        first.method_digest,
        first.suite_fingerprint,
        first.rank_of,
        first.tie_method,
        first.direction,
        first.scale_min,
        first.scale_max,
        first.unit,
    )
    for ranking in rankings[1:]:
        candidate = (
            ranking.cohort_id,
            ranking.metric_id,
            ranking.dimension_id,
            ranking.cap_id,
            ranking.cap_version,
            ranking.method_version,
            ranking.method_digest,
            ranking.suite_fingerprint,
            ranking.rank_of,
            ranking.tie_method,
            ranking.direction,
            ranking.scale_min,
            ranking.scale_max,
            ranking.unit,
        )
        if candidate != signature:
            raise ReleaseGateError("metric ranking cohort is inconsistent")
    members = {
        (str(ranking.provider_id), str(ranking.access_path_id)) for ranking in rankings
    }
    if len(members) != first.rank_of or len(rankings) != first.rank_of:
        raise ReleaseGateError("metric ranking requires a complete frozen cohort")
    if first.tie_method == "ordinal" and {ranking.rank for ranking in rankings} != set(
        range(1, first.rank_of + 1)
    ):
        raise ReleaseGateError(
            "ordinal metric ranking requires unique contiguous ranks"
        )
    if min(ranking.rank for ranking in rankings) != 1:
        raise ReleaseGateError("metric ranking must start at rank 1")


def _validate_provider_negative_attribution(
    cells: tuple[RunCell, ...],
) -> None:
    invalid = []
    for cell in cells:
        if cell.state is not CellState.PROVIDER_NEGATIVE:
            continue
        try:
            ensure_provider_side_attribution(cell.failure_attribution)
        except AttributionError:
            invalid.append(cell.run_key)
    if invalid:
        raise ReleaseGateError(
            "provider_negative cells require a provider-side failure attribution: "
            + ", ".join(invalid)
        )
