from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qveris_bench.catalog.validation import validate_cap_file
from qveris_bench.models.enums import QualificationDisposition
from qveris_bench.models.provider import AccessPath
from qveris_bench.models.run import RunPlan
from qveris_bench.models.suite import BenchmarkCase, BenchmarkSuite
from qveris_bench.providers.repository import (
    ProviderRegistryEntry,
    ProviderRegistryRepository,
)
from qveris_bench.suites.fingerprint import (
    assert_resume_fingerprint,
    canonical_json_bytes,
    suite_fingerprint,
)
from qveris_bench.suites.loader import load_cases, load_suite
from qveris_bench.suites.matrix import expand_run_plan


class SuiteCompilationError(ValueError):
    pass


@dataclass(frozen=True)
class CompiledSuite:
    suite: BenchmarkSuite
    cases: tuple[BenchmarkCase, ...]
    access_paths: tuple[AccessPath, ...]
    snapshot: dict[str, Any]
    fingerprint: str
    run_plan: RunPlan

    def assert_resume_fingerprint(self, fingerprint: str) -> None:
        assert_resume_fingerprint(self.fingerprint, fingerprint)


def _resolve_cases(
    suite: BenchmarkSuite, available: tuple[BenchmarkCase, ...]
) -> tuple[BenchmarkCase, ...]:
    case_index = {case.case_id: case for case in available}
    missing = [case_id for case_id in suite.case_ids if case_id not in case_index]
    if missing:
        raise SuiteCompilationError("missing cases: " + ", ".join(missing))
    cases = tuple(case_index[case_id] for case_id in suite.case_ids)
    mismatched = [case.case_id for case in cases if case.cap_id != suite.cap_id]
    if mismatched:
        raise SuiteCompilationError(
            "cases reference another CAP: " + ", ".join(mismatched)
        )
    return cases


def _resolve_access_paths(
    suite: BenchmarkSuite, records: tuple[ProviderRegistryEntry, ...]
) -> tuple[AccessPath, ...]:
    path_index: dict[str, tuple[AccessPath, ProviderRegistryEntry]] = {}
    for record in records:
        for access_path in record.access_paths:
            path_index[access_path.access_path_id] = (access_path, record)
    missing = [
        path_id for path_id in suite.access_path_ids if path_id not in path_index
    ]
    if missing:
        raise SuiteCompilationError("missing Access Paths: " + ", ".join(missing))
    resolved = []
    for path_id in suite.access_path_ids:
        access_path, record = path_index[path_id]
        if (
            access_path.qualification is None
            or access_path.qualification.disposition
            is not QualificationDisposition.INCLUDED
        ):
            raise SuiteCompilationError(f"Access Path is not included: {path_id}")
        if (
            suite.agent_protocol is not None
            and access_path.agent_trial_eligible
            and access_path.canonical_interface != suite.agent_protocol.canonical_tool
        ):
            raise SuiteCompilationError(
                f"Agent canonical tool {suite.agent_protocol.canonical_tool} does not "
                f"match {path_id} interface {access_path.canonical_interface}"
            )
        resolved.append(access_path)
    return tuple(resolved)


def _snapshot(
    suite: BenchmarkSuite,
    cases: tuple[BenchmarkCase, ...],
    access_paths: tuple[AccessPath, ...],
    records: tuple[ProviderRegistryEntry, ...],
) -> dict[str, Any]:
    return {
        "suite": suite.model_dump(mode="json"),
        "cases": [case.model_dump(mode="json") for case in cases],
        "access_paths": [path.model_dump(mode="json") for path in access_paths],
        "provider_cohort": [record.model_dump(mode="json") for record in records],
    }


def compile_suite(
    suite_path: Path,
    cases_path: Path,
    providers_root: Path,
    cap_path: Path | None = None,
) -> CompiledSuite:
    suite = load_suite(suite_path)
    resolved_cap_path = cap_path or suite_path.with_name("cap.yaml")
    try:
        cap = validate_cap_file(resolved_cap_path)
    except ValueError as exc:
        raise SuiteCompilationError(str(exc)) from exc
    if cap.cap_id != suite.cap_id or cap.version != suite.cap_version:
        raise SuiteCompilationError(
            f"suite CAP {suite.cap_id}@{suite.cap_version} does not match "
            f"{cap.cap_id}@{cap.version}"
        )
    cases = _resolve_cases(suite, load_cases(cases_path))
    records = ProviderRegistryRepository(providers_root).cohort_check()
    access_paths = _resolve_access_paths(suite, records)
    snapshot = _snapshot(suite, cases, access_paths, records)
    fingerprint = suite_fingerprint(snapshot)
    run_plan = expand_run_plan(suite, cases, access_paths, fingerprint)
    return CompiledSuite(
        suite=suite,
        cases=cases,
        access_paths=access_paths,
        snapshot=snapshot,
        fingerprint=fingerprint,
        run_plan=run_plan,
    )


def write_frozen_suite(compiled: CompiledSuite, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        canonical_json_bytes(
            {"fingerprint": compiled.fingerprint, "snapshot": compiled.snapshot}
        )
    )


def write_run_plan(compiled: CompiledSuite, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(compiled.run_plan.model_dump(mode="json")))
