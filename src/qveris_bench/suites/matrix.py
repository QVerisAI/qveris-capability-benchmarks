from __future__ import annotations

from qveris_bench.models.enums import CellState, RunMode
from qveris_bench.models.provider import AccessPath
from qveris_bench.models.run import RunCell, RunPlan
from qveris_bench.models.suite import BenchmarkCase, BenchmarkSuite


def canonical_run_key(
    suite_id: str,
    suite_fingerprint: str,
    *,
    case_id: str,
    provider_id: str,
    access_path_id: str,
    mode: RunMode,
    round_number: int,
) -> str:
    return ":".join(
        (
            suite_id,
            suite_fingerprint[:12],
            case_id,
            provider_id,
            access_path_id,
            mode.value,
            str(round_number),
        )
    )


def _applicability_reason(
    suite: BenchmarkSuite,
    case: BenchmarkCase,
    access_path: AccessPath,
    mode: RunMode,
) -> str | None:
    for rule in suite.not_applicable:
        if (
            rule.case_id == case.case_id
            and rule.access_path_id == access_path.access_path_id
            and (rule.mode is None or rule.mode is mode)
        ):
            return rule.reason
    if case.applicable_provider_ids and access_path.provider_id not in (
        case.applicable_provider_ids
    ):
        return "Case does not apply to this Provider."
    if mode is RunMode.AGENT_TRIAL and not access_path.agent_trial_eligible:
        return "Access Path is not eligible for Agent Trial."
    return None


def expand_run_plan(
    suite: BenchmarkSuite,
    cases: tuple[BenchmarkCase, ...],
    access_paths: tuple[AccessPath, ...],
    fingerprint: str,
) -> RunPlan:
    cells = []
    for case in cases:
        for access_path in access_paths:
            for mode in suite.modes:
                reason = _applicability_reason(suite, case, access_path, mode)
                for round_number in range(1, suite.rounds + 1):
                    run_key = canonical_run_key(
                        suite.suite_id,
                        fingerprint,
                        case_id=case.case_id,
                        provider_id=access_path.provider_id,
                        access_path_id=access_path.access_path_id,
                        mode=mode,
                        round_number=round_number,
                    )
                    cells.append(
                        RunCell(
                            run_key=run_key,
                            case_id=case.case_id,
                            case_input=case.input,
                            provider_id=access_path.provider_id,
                            access_path_id=access_path.access_path_id,
                            mode=mode,
                            round=round_number,
                            applicable=reason is None,
                            applicability_reason=reason,
                            state=(
                                CellState.PLANNED
                                if reason is None
                                else CellState.NOT_APPLICABLE
                            ),
                        )
                    )
    return RunPlan(
        suite_id=suite.suite_id,
        suite_fingerprint=fingerprint,
        cells=_require_unique_run_keys(cells),
    )


def _require_unique_run_keys(cells: list[RunCell]) -> tuple[RunCell, ...]:
    keys = [cell.run_key for cell in cells]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError("duplicate run_key: " + ", ".join(duplicates))
    return tuple(cells)
