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
    RunMode,
)
from qveris_bench.models.selection import (
    AgentInterfaceSnapshot,
    GatewayMetricsSnapshot,
    MarketCoverageResult,
    MarketCoverageSnapshot,
    MarketResultState,
    ObservationWindow,
    OfficialPricingSnapshot,
    QVerisListPriceSnapshot,
    RunObservationsSnapshot,
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
        compiled = compile_suite(
            suite_path,
            cases_path,
            providers_root,
            suite_path.with_name("cap.yaml"),
        )
        suite = compiled.suite
        cases = compiled.cases
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

    window = ObservationWindow.model_validate(_mapping(config, "observation_window"))
    edition = date.fromisoformat(_string(config, "edition"))
    if suite.environment.get("as_of") != window.start.isoformat() or (
        window.start != window.end
    ):
        raise SelectionSnapshotBuildError(
            "observation window does not match suite as_of"
        )
    market_spec = _mapping(config, "market_coverage_release")
    market_release_path = root / _string(market_spec, "release")
    market_release_bytes = market_release_path.read_bytes()
    market_release_digest = release_digest(market_release_bytes)
    if market_release_digest != _string(market_spec, "digest"):
        raise SelectionSnapshotBuildError("market coverage release digest mismatch")
    market_suite_path = root / _string(market_spec, "suite")
    market_cases_path = root / _string(market_spec, "cases")
    market_compiled = compile_suite(
        market_suite_path,
        market_cases_path,
        providers_root,
        market_suite_path.with_name("cap.yaml"),
    )
    market_release = json.loads(market_release_bytes)
    market_release_metadata = market_release.get("release")
    if not isinstance(market_release_metadata, dict) or (
        market_release_metadata.get("suite_fingerprint") != market_compiled.fingerprint
    ):
        raise SelectionSnapshotBuildError("market suite fingerprint mismatch")
    market_cells = [
        item
        for item in market_release.get("cells", [])
        if isinstance(item, dict) and str(item.get("mode")) == RunMode.DIRECT.value
    ]
    market_evidence = [
        item for item in market_release.get("evidence", []) if isinstance(item, dict)
    ]
    _validate_release_projection(
        market_release,
        market_cells,
        market_evidence,
        market_compiled.suite.suite_id,
    )
    try:
        replay_release_dir(
            market_release_path.parent,
            expected_digest=market_release_digest,
        )
    except ReleaseReplayError as exc:
        raise SelectionSnapshotBuildError(
            f"market coverage release replay failed: {exc}"
        ) from exc
    market_cases = {case.case_id: case for case in market_compiled.cases}
    market_evidence_by_run_key = {
        str(item["run_key"]): item for item in market_evidence
    }
    market_identity_cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for cell in market_cells:
        identity = (str(cell["provider_id"]), str(cell["access_path_id"]))
        market_identity_cells.setdefault(identity, []).append(cell)
    if market_identity_cells.keys() != identity_cells.keys():
        raise SelectionSnapshotBuildError(
            "market coverage identities do not match selection identities"
        )
    market_observation_date = date.fromisoformat(
        str(market_compiled.suite.environment.get("as_of"))
    )
    list_pricing_spec = _mapping(config, "qveris_list_pricing")
    list_pricing_path = root / _string(list_pricing_spec, "snapshot")
    list_pricing_digest = _sha256(list_pricing_path)
    bindings_path = root / _string(list_pricing_spec, "bindings")
    list_prices = _load_qveris_list_prices(
        list_pricing_path,
        bindings_path,
        edition=edition,
    )
    qveris_identities = {
        identity
        for identity in identity_cells
        if next(
            item
            for item in registry_by_id[identity[0]].access_paths
            if item.access_path_id == identity[1]
        ).path_type
        is AccessPathType.QVERIS_CONNECTOR
    }
    if set(list_prices) != qveris_identities:
        raise SelectionSnapshotBuildError(
            "QVeris list pricing identities do not match selection identities"
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
                qveris_list_price=(
                    QVerisListPriceSnapshot(
                        state="declared",
                        amount_credits=list_prices[(provider_id, access_path_id)][
                            "amount_credits"
                        ],
                        unit="per_call",
                        source="qveris_inspect",
                        inspected_at=list_prices[(provider_id, access_path_id)][
                            "inspected_at"
                        ],
                        snapshot_version=list_prices[(provider_id, access_path_id)][
                            "snapshot_version"
                        ],
                        evidence_ref=list_pricing_digest,
                    )
                    if is_qveris
                    else QVerisListPriceSnapshot(state="not_applicable")
                ),
                official_pricing=_pricing(
                    record.provider.official_pricing, access_path_id
                ),
                market_coverage=_market_coverage(
                    market_identity_cells[(provider_id, access_path_id)],
                    market_cases,
                    market_evidence_by_run_key,
                    market_release_digest,
                    market_observation_date,
                ),
                agent_interface=_agent_interface(
                    scoped_cells, case_roles, evidence_by_run_key
                ),
            )
        )

    snapshot = SelectionSnapshot(
        snapshot_id=_string(config, "snapshot_id"),
        version=_string(config, "version"),
        edition=edition,
        cap_id=cap_id,
        cap_release_digest=actual_release_digest,
        market_coverage_release_digest=market_release_digest,
        input_digests={
            "input": _sha256(input_path),
            "release": actual_release_digest,
            "cases": _sha256(cases_path),
            "suite": _sha256(suite_path),
            "providers": provider_digests,
            "market_coverage_release": market_release_digest,
            "market_coverage_suite": _sha256(market_suite_path),
            "market_coverage_cases": _sha256(market_cases_path),
            "qveris_list_pricing": list_pricing_digest,
            "qveris_direct_bindings": _sha256(bindings_path),
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


def _load_qveris_list_prices(
    snapshot_path: Path,
    bindings_path: Path,
    *,
    edition: date,
) -> dict[tuple[str, str], dict[str, Any]]:
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectionSnapshotBuildError("invalid QVeris list pricing input") from exc
    if snapshot.get("source") != "qveris_inspect" or snapshot.get(
        "bindings_digest"
    ) != _sha256(bindings_path):
        raise SelectionSnapshotBuildError("QVeris list pricing provenance mismatch")
    inspected_at = date.fromisoformat(str(snapshot.get("inspected_at")))
    if inspected_at > edition:
        raise SelectionSnapshotBuildError("QVeris list pricing is newer than edition")
    binding_identities: dict[tuple[str, str], str] = {}
    for binding in bindings.get("bindings", []):
        if binding.get("transport") != "qveris_connector":
            continue
        identity = (str(binding.get("provider_id")), str(binding.get("access_path_id")))
        tool_id = str(binding.get("tool_id"))
        previous = binding_identities.setdefault(identity, tool_id)
        if previous != tool_id:
            raise SelectionSnapshotBuildError("Access Path has multiple QVeris tools")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for fact in snapshot.get("prices", []):
        if not isinstance(fact, dict):
            raise SelectionSnapshotBuildError("invalid QVeris list price fact")
        identity = (str(fact.get("provider_id")), str(fact.get("access_path_id")))
        if (
            identity in result
            or binding_identities.get(identity) != fact.get("tool_id")
        ):
            raise SelectionSnapshotBuildError("QVeris list price identity mismatch")
        amount = fact.get("amount_credits")
        snapshot_version = fact.get("snapshot_version")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or amount < 0
            or not isinstance(snapshot_version, str)
            or not snapshot_version
        ):
            raise SelectionSnapshotBuildError("invalid QVeris list price amount")
        result[identity] = {
            "amount_credits": float(amount),
            "inspected_at": inspected_at,
            "snapshot_version": snapshot_version,
        }
    return result


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
    cases: dict[str, Any],
    evidence_by_run_key: dict[str, dict[str, Any]],
    release_digest_value: str,
    observation_date: date,
) -> MarketCoverageSnapshot:
    by_market: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        case_id = str(cell["case_id"])
        case = cases.get(case_id)
        if case is None:
            raise SelectionSnapshotBuildError("market release references unknown case")
        if case.negative_control:
            continue
        market = case.input.get("market")
        if not isinstance(market, str):
            raise SelectionSnapshotBuildError("market case is missing market identity")
        by_market.setdefault(market, []).append(cell)
    results = []
    for market, scoped in sorted(by_market.items()):
        total = len(scoped)
        if all(not cell.get("applicable") for cell in scoped):
            reasons = {str(cell.get("applicability_reason")) for cell in scoped}
            if len(reasons) != 1 or None in reasons:
                raise SelectionSnapshotBuildError(
                    "not-applicable market requires one frozen reason"
                )
            results.append(
                MarketCoverageResult(
                    market=market,
                    state="not_applicable",
                    passed_rounds=0,
                    total_rounds=total,
                    applicability_reason=next(iter(reasons)),
                )
            )
            continue
        if any(not cell.get("applicable") for cell in scoped):
            raise SelectionSnapshotBuildError("market applicability differs by round")
        refs = tuple(
            sorted(
                str(evidence_by_run_key[str(cell["run_key"])]["public_digest"])
                for cell in scoped
            )
        )
        states = {str(cell.get("state")) for cell in scoped}
        if states == {CellState.COMPLETED.value}:
            state: MarketResultState = "verified"
            passed = total
        elif states == {CellState.PROVIDER_NEGATIVE.value}:
            state = "provider_negative"
            passed = 0
        else:
            raise SelectionSnapshotBuildError(
                f"market rounds disagree for {market}: {sorted(states)}"
            )
        results.append(
            MarketCoverageResult(
                market=market,
                state=state,
                passed_rounds=passed,
                total_rounds=total,
                evidence_refs=refs,
            )
        )
    return MarketCoverageSnapshot(
        release_digest=release_digest_value,
        observation_date=observation_date,
        results=tuple(results),
    )


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
