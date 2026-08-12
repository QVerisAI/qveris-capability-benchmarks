from __future__ import annotations

from qveris_bench.evidence.policy import PublicationPolicyError, validate_publication
from qveris_bench.models.enums import CellState, DimensionState
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.metric import (
    MetricDefinition,
    MetricRanking,
    MetricScore,
    metric_definition_digest,
    metric_ranking_cohort_digest,
)
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
    metric_registry: tuple[MetricDefinition, ...] = (),
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
    _validate_metrics(release, cells, evidence, metric_registry)
    if require_attribution:
        _validate_provider_negative_attribution(cells)


def _validate_metrics(
    release: BenchmarkRelease,
    cells: tuple[RunCell, ...],
    evidence: tuple[EvidenceBundle, ...],
    metric_registry: tuple[MetricDefinition, ...],
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
    if metrics and (release.cap_id is None or release.cap_version is None):
        raise ReleaseGateError("release metrics require one CAP identity")
    released_definitions = {
        metric_definition_digest(definition): definition
        for definition in release.metric_definitions
    }
    if len(released_definitions) != len(release.metric_definitions):
        raise ReleaseGateError("duplicate registered CAP metric definition")
    definitions = {
        metric_definition_digest(definition): definition
        for definition in metric_registry
    }
    if metrics and not definitions:
        raise ReleaseGateError("release metrics require a CAP-owned metric registry")
    if released_definitions != definitions:
        raise ReleaseGateError("release metric definitions do not match CAP registry")
    for metric in metrics:
        definition = definitions.get(str(metric.definition_digest))
        if definition is None:
            raise ReleaseGateError("metric requires a registered CAP metric definition")
        expected = (
            release.cap_id,
            release.cap_version,
            definition.cap_id,
            definition.cap_version,
            definition.metric_id,
            definition.dimension_id,
            definition.method_version,
            definition.method_digest,
            definition.scale_min,
            definition.scale_max,
            definition.unit,
            definition.direction,
        )
        actual = (
            metric.cap_id,
            metric.cap_version,
            metric.cap_id,
            metric.cap_version,
            metric.metric_id,
            metric.dimension_id,
            metric.method_version,
            metric.method_digest,
            metric.scale_min,
            metric.scale_max,
            metric.unit,
            metric.direction,
        )
        if actual != expected:
            raise ReleaseGateError(
                "metric does not match its registered CAP definition"
            )

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
        if any(
            metric_scopes_by_digest.get(str(reference)) != {metric_scope}
            for reference in metric.evidence_refs
        ):
            raise ReleaseGateError(
                "metric evidence does not match its Provider / Access Path"
            )

    scores_by_metric_scope = {
        (
            str(metric.definition_digest),
            str(metric.provider_id),
            str(metric.access_path_id),
        ): metric
        for metric in metrics
        if isinstance(metric, MetricScore)
    }
    rankings_by_metric_cohort: dict[tuple[str, str], list[MetricRanking]] = {}
    for metric in metrics:
        if isinstance(metric, MetricRanking):
            key = (str(metric.cohort_id), str(metric.definition_digest))
            rankings_by_metric_cohort.setdefault(key, []).append(metric)
    cohort_members: dict[str, set[tuple[str, str]]] = {}
    for rankings in rankings_by_metric_cohort.values():
        members = _validate_ranking_cohort(rankings, scores_by_metric_scope)
        cohort_id = str(rankings[0].cohort_id)
        if cohort_id in cohort_members and cohort_members[cohort_id] != members:
            raise ReleaseGateError("frozen cohort membership is inconsistent")
        cohort_members[cohort_id] = members


def _validate_ranking_cohort(
    rankings: list[MetricRanking],
    scores: dict[tuple[str, str, str], MetricScore],
) -> set[tuple[str, str]]:
    first = rankings[0]
    signature = (
        first.cohort_id,
        first.metric_id,
        first.definition_digest,
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
            ranking.definition_digest,
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
    if any(ranking.cohort_digest != first.cohort_digest for ranking in rankings):
        raise ReleaseGateError("metric ranking cohort digest mismatch")
    if str(first.cohort_digest) != metric_ranking_cohort_digest(rankings):
        raise ReleaseGateError("metric ranking cohort digest mismatch")
    if first.tie_method == "ordinal" and {ranking.rank for ranking in rankings} != set(
        range(1, first.rank_of + 1)
    ):
        raise ReleaseGateError(
            "ordinal metric ranking requires unique contiguous ranks"
        )
    if min(ranking.rank for ranking in rankings) != 1:
        raise ReleaseGateError("metric ranking must start at rank 1")
    ordered_counts: dict[int, int] = {}
    for ranking in rankings:
        ordered_counts[ranking.rank] = ordered_counts.get(ranking.rank, 0) + 1
    ranks = sorted(ordered_counts)
    if first.tie_method == "dense" and ranks != list(range(1, len(ranks) + 1)):
        raise ReleaseGateError("dense metric ranking requires contiguous rank levels")
    if first.tie_method == "competition":
        expected: list[int] = []
        position = 1
        for rank in ranks:
            expected.append(position)
            position += ordered_counts[rank]
        if ranks != expected:
            raise ReleaseGateError("competition metric ranking has invalid tie gaps")
    score_values: list[tuple[float, MetricRanking]] = []
    for ranking in rankings:
        key = (
            str(ranking.definition_digest),
            str(ranking.provider_id),
            str(ranking.access_path_id),
        )
        score = scores.get(key)
        if score is None:
            raise ReleaseGateError("metric ranking requires a matching metric score")
        score_values.append((score.value, ranking))
    reverse = first.direction == "higher_is_better"
    ordered = sorted(score_values, key=lambda item: item[0], reverse=reverse)
    expected_ranks: dict[tuple[str, str], int] = {}
    dense_rank = 0
    previous_value: float | None = None
    for position, (value, ranking) in enumerate(ordered, start=1):
        if previous_value is None or value != previous_value:
            dense_rank += 1
        expected_rank = dense_rank if first.tie_method == "dense" else position
        if first.tie_method == "competition" and value == previous_value:
            expected_rank = expected_ranks[
                (
                    str(ordered[position - 2][1].provider_id),
                    str(ordered[position - 2][1].access_path_id),
                )
            ]
        expected_ranks[(str(ranking.provider_id), str(ranking.access_path_id))] = (
            expected_rank
        )
        previous_value = value
    if first.tie_method == "ordinal":
        values = [value for value, _ in ordered]
        if len(values) != len(set(values)):
            raise ReleaseGateError("ordinal metric ranking cannot contain score ties")
    if any(
        ranking.rank
        != expected_ranks[(str(ranking.provider_id), str(ranking.access_path_id))]
        for ranking in rankings
    ):
        raise ReleaseGateError("metric ranking does not match metric score ordering")
    return members


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
