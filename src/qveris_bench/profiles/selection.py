from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any

from pydantic import ValidationError

from qveris_bench.models.enums import (
    AccessPathType,
    CellState,
    DisclosureLevel,
    LicenseStatus,
    RunMode,
)
from qveris_bench.models.selection import (
    AgentInterfaceSnapshot,
    GatewayMetricsSnapshot,
    MarketCoverageSnapshot,
    MeasurementState,
    ObservationWindow,
    OfficialPricingSnapshot,
    RunObservationsSnapshot,
    ScopeValidationSnapshot,
    SelectionMarketScope,
    SelectionObservation,
    SelectionSnapshot,
    SelectionSnapshotRow,
)
from qveris_bench.providers.repository import ProviderRegistryRepository
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.replay import ReleaseReplayError, replay_release_dir
from qveris_bench.suites.compiler import SuiteCompilationError, compile_suite
from qveris_bench.suites.fingerprint import canonical_json_bytes
from qveris_bench.suites.matrix import canonical_run_key
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping


class SelectionSnapshotBuildError(ValueError):
    pass


@dataclass(frozen=True)
class SelectionSnapshotBuild:
    snapshot: SelectionSnapshot
    json_bytes: bytes


def build_selection_snapshot(input_path: Path, root: Path) -> SelectionSnapshotBuild:
    try:
        config = load_yaml_mapping(input_path)
        release_spec = _mapping(config, "cap_release")
        release_path = root / _string(release_spec, "release")
        release_bytes = release_path.read_bytes()
        actual_release_digest = release_digest(release_bytes)
        expected_release_digest = _string(release_spec, "digest")
        if actual_release_digest != expected_release_digest:
            raise SelectionSnapshotBuildError(
                f"release digest mismatch: {actual_release_digest}"
            )
        release = json.loads(release_bytes)
        providers_root = root / _string(config, "providers_root")
        suite_path = root / _string(config, "suite")
        cases_path = root / _string(config, "cases")
        case_markets_path = root / _string(config, "case_markets")
        compiled = compile_suite(
            suite_path,
            cases_path,
            providers_root,
            suite_path.with_name("cap.yaml"),
        )
        suite = compiled.suite
        cases = compiled.cases
        case_markets = SelectionMarketScope.model_validate(
            load_yaml_mapping(case_markets_path)
        )
    except (
        OSError,
        json.JSONDecodeError,
        YamlDocumentError,
        SuiteCompilationError,
        ValidationError,
        ValueError,
    ) as exc:
        if isinstance(exc, SelectionSnapshotBuildError):
            raise
        raise SelectionSnapshotBuildError(
            f"invalid selection snapshot input: {exc}"
        ) from exc

    cap_id = _string(config, "cap_id")
    if cap_id != suite.cap_id:
        raise SelectionSnapshotBuildError("selection CAP does not match suite CAP")
    cases_by_id = {case.case_id: case for case in cases}
    if set(cases_by_id) != set(suite.case_ids):
        raise SelectionSnapshotBuildError("selection cases do not match suite cases")
    if any(case.cap_id != cap_id for case in cases):
        raise SelectionSnapshotBuildError("selection case belongs to another CAP")
    case_roles = {case.case_id: case.negative_control for case in cases}
    if case_markets.cap_id != cap_id:
        raise SelectionSnapshotBuildError("market metadata belongs to another CAP")
    market_by_case = {item.case_id: item.market for item in case_markets.cases}
    expected_market_cases = {
        case.case_id for case in cases if not case.negative_control
    }
    if len(market_by_case) != len(case_markets.cases) or (
        set(market_by_case) != expected_market_cases
    ):
        raise SelectionSnapshotBuildError(
            "market metadata does not match positive cases"
        )
    cells = [item for item in release.get("cells", []) if isinstance(item, dict)]
    evidence = [item for item in release.get("evidence", []) if isinstance(item, dict)]
    release_metadata = release.get("release")
    if not isinstance(release_metadata, dict) or (
        compiled.fingerprint != release_metadata.get("suite_fingerprint")
    ):
        raise SelectionSnapshotBuildError("compiled suite fingerprint mismatch")
    _validate_release_projection(release, cells, evidence, suite.suite_id)
    try:
        replay_release_dir(release_path.parent, expected_digest=actual_release_digest)
    except ReleaseReplayError as exc:
        raise SelectionSnapshotBuildError(f"release replay failed: {exc}") from exc
    cells = [item for item in cells if str(item.get("mode")) == RunMode.DIRECT.value]
    evidence_by_run_key = {str(item["run_key"]): item for item in evidence}
    registry = ProviderRegistryRepository(providers_root).list()
    registry_by_id = {item.provider_id: item for item in registry}
    identity_cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for cell in cells:
        if not cell.get("applicable"):
            continue
        identity = (str(cell["provider_id"]), str(cell["access_path_id"]))
        identity_cells.setdefault(identity, []).append(cell)

    sv_spec = _mapping(config, "qveris_sv")
    sv_namespace = _string(sv_spec, "namespace")
    window = ObservationWindow.model_validate(_mapping(config, "observation_window"))
    if suite.environment.get("as_of") != window.start.isoformat() or (
        window.start != window.end
    ):
        raise SelectionSnapshotBuildError(
            "observation window does not match suite as_of"
        )
    sv_results, sv_digest = _load_sv_results(sv_spec, root, sv_namespace, window)
    unknown_sv_identities = set(sv_results) - set(identity_cells)
    if unknown_sv_identities:
        provider_id, access_path_id = sorted(unknown_sv_identities)[0]
        raise SelectionSnapshotBuildError(
            f"unknown SV identity: {provider_id}/{access_path_id}"
        )
    rows: list[SelectionSnapshotRow] = []
    provider_digests: dict[str, str] = {}
    for (provider_id, access_path_id), scoped_cells in sorted(identity_cells.items()):
        record = registry_by_id.get(provider_id)
        if record is None:
            raise SelectionSnapshotBuildError(f"unknown Provider: {provider_id}")
        access_path = next(
            (
                item
                for item in record.access_paths
                if item.access_path_id == access_path_id
            ),
            None,
        )
        if access_path is None:
            raise SelectionSnapshotBuildError(
                f"unknown Provider/Access Path: {provider_id}/{access_path_id}"
            )
        provider_path = providers_root / provider_id / "provider.yaml"
        provider_digests[provider_id] = _sha256(provider_path)
        public_evidence = [
            evidence_by_run_key[str(cell["run_key"])]
            for cell in scoped_cells
            if str(cell["run_key"]) in evidence_by_run_key
        ]
        refs = tuple(
            sorted(
                str(item["public_digest"])
                for item in public_evidence
                if item.get("public_digest")
            )
        )
        is_qveris = access_path.path_type is AccessPathType.QVERIS_CONNECTOR
        rows.append(
            SelectionSnapshotRow(
                cap_id=cap_id,
                provider_id=provider_id,
                provider_name=record.provider.official_name,
                access_path_id=access_path_id,
                access_path_type=access_path.path_type,
                observation_window=window,
                run_observations=_run_observations(scoped_cells, refs),
                gateway_metrics=_gateway_metrics(
                    scoped_cells,
                    evidence_by_run_key,
                    case_roles,
                    is_qveris=is_qveris,
                ),
                official_pricing=_pricing(
                    record.provider.official_pricing, access_path_id
                ),
                market_coverage=_market_coverage(
                    scoped_cells,
                    case_roles,
                    market_by_case,
                    evidence_by_run_key,
                    sv_namespace,
                    sv_results.get((provider_id, access_path_id), []),
                    sv_applicable=is_qveris,
                ),
                agent_interface=_agent_interface(
                    scoped_cells, case_roles, evidence_by_run_key
                ),
            )
        )

    snapshot = SelectionSnapshot(
        snapshot_id=_string(config, "snapshot_id"),
        version=_string(config, "version"),
        edition=date.fromisoformat(_string(config, "edition")),
        cap_id=cap_id,
        cap_release_digest=actual_release_digest,
        input_digests={
            "input": _sha256(input_path),
            "release": actual_release_digest,
            "cases": _sha256(cases_path),
            "case_markets": _sha256(case_markets_path),
            "suite": _sha256(suite_path),
            "providers": provider_digests,
            "qveris_sv": sv_digest,
        },
        rows=tuple(rows),
        limitations=tuple(str(item) for item in config.get("limitations", [])),
    )
    return SelectionSnapshotBuild(
        snapshot=snapshot,
        json_bytes=canonical_json_bytes(snapshot.model_dump(mode="json")),
    )


def _gateway_metrics(
    cells: list[dict[str, Any]],
    evidence_by_run_key: dict[str, dict[str, Any]],
    case_roles: dict[str, bool],
    *,
    is_qveris: bool,
) -> GatewayMetricsSnapshot:
    if not is_qveris:
        return GatewayMetricsSnapshot(
            state="not_applicable",
            latency_sample_size=0,
            cost_sample_size=0,
        )
    latency_evidence = [
        evidence_by_run_key[str(cell["run_key"])]
        for cell in cells
        if str(cell["run_key"]) in evidence_by_run_key
    ]
    cost_evidence = [
        evidence_by_run_key[str(cell["run_key"])]
        for cell in cells
        if not case_roles.get(str(cell["case_id"]), False)
        and str(cell.get("state")) == CellState.COMPLETED.value
        and str(cell["run_key"]) in evidence_by_run_key
    ]
    latencies = sorted(
        float(item["latency_ms"])
        for item in latency_evidence
        if isinstance(item.get("latency_ms"), (int, float))
    )
    costs = sorted(
        float(item["cost_credits"])
        for item in cost_evidence
        if isinstance(item.get("cost_credits"), (int, float))
    )
    latency_refs = _public_refs(latency_evidence, field="latency_ms")
    cost_refs = _public_refs(cost_evidence, field="cost_credits")
    return GatewayMetricsSnapshot(
        state="measured" if latencies else "evidence_insufficient",
        latency_sample_size=len(latencies),
        latency_min_ms=min(latencies) if latencies else None,
        latency_median_ms=median(latencies) if latencies else None,
        latency_max_ms=max(latencies) if latencies else None,
        cost_sample_size=len(costs),
        median_credits=median(costs) if costs else None,
        evidence_refs=tuple(sorted(set(latency_refs + cost_refs))) if latencies else (),
        latency_evidence_refs=latency_refs,
        cost_evidence_refs=cost_refs,
    )


def _run_observations(
    cells: list[dict[str, Any]], refs: tuple[str, ...]
) -> RunObservationsSnapshot:
    terminal = {
        CellState.COMPLETED.value,
        CellState.PROVIDER_NEGATIVE.value,
        CellState.EXCLUDED.value,
    }
    count = sum(str(item.get("state")) in terminal for item in cells)
    return RunObservationsSnapshot(
        state="measured",
        terminal_observations=count,
        planned_observations=len(cells),
        evidence_refs=refs,
    )


def _pricing(
    pricing_facts: tuple[Any, ...], access_path_id: str
) -> OfficialPricingSnapshot:
    matches = [
        item
        for item in pricing_facts
        if item.applies_to == "provider_wide" or access_path_id in item.applies_to
    ]
    if not matches:
        return OfficialPricingSnapshot(state="evidence_insufficient")
    if len(matches) != 1:
        raise SelectionSnapshotBuildError(
            f"multiple pricing facts apply to Access Path: {access_path_id}"
        )
    item = matches[0]
    return OfficialPricingSnapshot(
        state="declared",
        pricing_id=item.pricing_id,
        pricing_url=item.pricing_url,
        free_tier=item.free_tier,
        paid_plans=item.paid_plans,
        verified_at=item.verified_at,
        source_digest=item.source_digest,
        applies_to=item.applies_to,
        currencies=item.currencies,
        extractor_version=item.extractor_version,
        suite_fingerprint=item.suite_fingerprint,
        disclosure_level=item.disclosure_level.value,
        license_status=item.license_status.value,
    )


def _agent_interface(
    cells: list[dict[str, Any]],
    case_roles: dict[str, bool],
    evidence_by_run_key: dict[str, dict[str, Any]],
) -> AgentInterfaceSnapshot:
    negative_cells = [
        item for item in cells if case_roles.get(str(item["case_id"]), False)
    ]
    passed = sum(
        str(item.get("state")) == CellState.COMPLETED.value for item in negative_cells
    )
    refs = tuple(
        sorted(
            str(evidence_by_run_key[str(item["run_key"])]["public_digest"])
            for item in negative_cells
            if str(item["run_key"]) in evidence_by_run_key
            and evidence_by_run_key[str(item["run_key"])].get("public_digest")
        )
    )
    insufficient = SelectionObservation(state="evidence_insufficient")
    return AgentInterfaceSnapshot(
        invalid_input_handling=SelectionObservation(
            state="measured",
            passed=passed,
            total=len(negative_cells),
            evidence_refs=refs,
        ),
        parameter_clarity=insufficient,
        schema_stability=insufficient,
        pagination=insufficient,
        single_tool_completion=insufficient,
    )


def _market_coverage(
    cells: list[dict[str, Any]],
    case_roles: dict[str, bool],
    market_by_case: dict[str, Any],
    evidence_by_run_key: dict[str, dict[str, Any]],
    namespace: str,
    sv_results: list[dict[str, Any]],
    *,
    sv_applicable: bool,
) -> MarketCoverageSnapshot:
    tested: set[str] = set()
    refs: set[str] = set()
    for cell in cells:
        case_id = str(cell["case_id"])
        if case_roles.get(case_id, False) or case_id not in market_by_case:
            continue
        tested.add(str(market_by_case[case_id]))
        evidence = evidence_by_run_key.get(str(cell["run_key"]))
        if evidence and evidence.get("public_digest"):
            refs.add(str(evidence["public_digest"]))
    if not sv_applicable:
        sv_state: MeasurementState = "not_applicable"
    elif sv_results:
        sv_state = "measured"
    else:
        sv_state = "evidence_insufficient"
    return MarketCoverageSnapshot(
        tested_markets=tuple(sorted(tested)),
        tested_evidence_refs=tuple(sorted(refs)),
        sv_namespace=namespace,
        sv_state=sv_state,
        sv_verified_markets=tuple(
            sorted(str(item["market"]) for item in sv_results if item.get("supported"))
        ),
        sv_evidence_refs=tuple(
            sorted(str(item["evidence_ref"]) for item in sv_results)
        ),
    )


def _load_sv_results(
    spec: dict[str, Any],
    root: Path,
    expected_namespace: str,
    expected_window: ObservationWindow,
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], str | None]:
    relative = spec.get("snapshot")
    if relative is None:
        if spec.get("snapshot_digest") is not None:
            raise SelectionSnapshotBuildError("QVeris SV digest requires a snapshot")
        return {}, None
    if not isinstance(relative, str) or not relative:
        raise SelectionSnapshotBuildError("qveris_sv.snapshot must be a path or null")
    path = root / relative
    try:
        actual_digest = _sha256(path)
        if actual_digest != spec.get("snapshot_digest"):
            raise SelectionSnapshotBuildError("QVeris SV snapshot digest mismatch")
        snapshot = ScopeValidationSnapshot.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise SelectionSnapshotBuildError(f"invalid QVeris SV snapshot: {exc}") from exc
    if snapshot.namespace != expected_namespace:
        raise SelectionSnapshotBuildError("QVeris SV namespace mismatch")
    if snapshot.observation_window != expected_window:
        raise SelectionSnapshotBuildError("QVeris SV observation window mismatch")
    if (
        snapshot.disclosure_level is not DisclosureLevel.SANITIZED_PUBLIC
        or snapshot.license_status is not LicenseStatus.CLEARED
    ):
        raise SelectionSnapshotBuildError("QVeris SV requires publishable provenance")
    results: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for result in snapshot.results:
        identity = (result.provider_id, result.access_path_id)
        results.setdefault(identity, []).append(result.model_dump(mode="json"))
    return results, actual_digest


def _validate_release_projection(
    release: dict[str, Any],
    cells: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    suite_id: str,
) -> None:
    release_metadata = release.get("release")
    if not isinstance(release_metadata, dict):
        raise SelectionSnapshotBuildError("release metadata is missing")
    fingerprint = str(release_metadata.get("suite_fingerprint", ""))
    for cell in cells:
        try:
            expected = canonical_run_key(
                suite_id,
                fingerprint,
                case_id=str(cell["case_id"]),
                provider_id=str(cell["provider_id"]),
                access_path_id=str(cell["access_path_id"]),
                mode=RunMode(str(cell["mode"])),
                round_number=int(cell["round"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SelectionSnapshotBuildError("invalid release cell identity") from exc
        if cell.get("run_key") != expected:
            raise SelectionSnapshotBuildError("run key does not match release identity")
    applicable = {
        str(cell["run_key"])
        for cell in cells
        if cell.get("applicable") and str(cell.get("mode")) == RunMode.DIRECT.value
    }
    evidence_keys = [str(item.get("run_key")) for item in evidence]
    if len(evidence_keys) != len(set(evidence_keys)) or applicable != set(
        evidence_keys
    ):
        raise SelectionSnapshotBuildError("release evidence topology mismatch")


def _public_refs(evidence: list[dict[str, Any]], *, field: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(item["public_digest"])
            for item in evidence
            if isinstance(item.get(field), (int, float)) and item.get("public_digest")
        )
    )


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _mapping(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise SelectionSnapshotBuildError(f"{key} must be a mapping")
    return value


def _string(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise SelectionSnapshotBuildError(f"{key} is required")
    return value
