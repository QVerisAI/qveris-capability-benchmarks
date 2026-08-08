from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from qveris_bench.models.enums import DimensionState
from qveris_bench.models.profile import ProfileDimension, TaskFitProfile
from qveris_bench.models.scenario import ScenarioRef
from qveris_bench.releases.canonical import release_digest
from qveris_bench.suites.fingerprint import canonical_json_bytes
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping


class ProfileBuildError(ValueError):
    pass


@dataclass(frozen=True)
class ProfileBuild:
    profile: TaskFitProfile
    json_bytes: bytes
    markdown_bytes: bytes


def build_profile(input_path: Path, root: Path) -> ProfileBuild:
    try:
        document = load_yaml_mapping(input_path)
        profile_id = _required(document, "profile_id")
        version = _required(document, "version")
        scenario = document.get("scenario_ref")
        if not isinstance(scenario, dict):
            raise ProfileBuildError("scenario_ref must be a mapping")
        scenario_ref = ScenarioRef(
            scenario_id=_required(scenario, "scenario_id"),
            version=_required(scenario, "version"),
        )
        cap_releases = document.get("cap_releases")
        if not isinstance(cap_releases, dict) or not cap_releases:
            raise ProfileBuildError("cap_releases must be a non-empty mapping")
    except (YamlDocumentError, ValidationError, ValueError) as exc:
        raise ProfileBuildError(f"invalid profile input: {exc}") from exc

    dimensions: list[ProfileDimension] = []
    limitations: list[str] = []
    for cap_id in sorted(cap_releases):
        release_spec = cap_releases[cap_id]
        if not isinstance(release_spec, dict):
            raise ProfileBuildError(f"release spec for {cap_id} must be a mapping")
        release_path = root / _required(release_spec, "release")
        expected_digest = _required(release_spec, "digest")
        try:
            release_bytes = release_path.read_bytes()
        except OSError as exc:
            raise ProfileBuildError(f"release not found: {release_path}") from exc
        actual_digest = release_digest(release_bytes)
        if actual_digest != expected_digest:
            raise ProfileBuildError(
                f"release digest mismatch for {cap_id}: {actual_digest}"
            )
        document_release = json.loads(release_bytes)
        cells = document_release.get("cells", [])
        evidence = document_release.get("evidence", [])
        limitations.extend(
            str(item)
            for item in document_release.get("release", {}).get("limitations", [])
        )
        dimensions.extend(_case_dimensions(cap_id, cells, evidence))
        dimensions.extend(_gateway_dimensions(cap_id, evidence))
        dimensions.extend(_cap_level_insufficient(cap_id))

    profile = TaskFitProfile(
        profile_id=profile_id,
        version=version,
        scenario_ref=scenario_ref,
        cap_dimensions=tuple(dimensions),
        limitations=tuple(dict.fromkeys(limitations)),
    )
    json_bytes = canonical_json_bytes(profile.model_dump(mode="json"))
    return ProfileBuild(
        profile=profile,
        json_bytes=json_bytes,
        markdown_bytes=_markdown(profile).encode(),
    )


def _case_dimensions(
    cap_id: str, cells: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> tuple[ProfileDimension, ...]:
    evidence_by_run_key = {
        str(bundle.get("run_key")): str(bundle.get("public_digest"))
        for bundle in evidence
        if isinstance(bundle, dict) and bundle.get("public_digest")
    }
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        if isinstance(cell, dict):
            by_case[str(cell.get("case_id"))].append(cell)
    dimensions: list[ProfileDimension] = []
    for case_id in sorted(by_case):
        case_cells = by_case[case_id]
        states = Counter(
            str(cell.get("state")) for cell in case_cells if isinstance(cell, dict)
        )
        refs: list[str] = []
        for cell in case_cells:
            run_key = str(cell.get("run_key"))
            if run_key in evidence_by_run_key:
                refs.append(evidence_by_run_key[run_key])
        dimensions.append(
            ProfileDimension(
                cap_id=cap_id,
                dimension=f"case:{case_id}:outcome",
                dimension_state=DimensionState.MEASURED,
                details={
                    "completed": states.get("completed", 0),
                    "provider_negative": states.get("provider_negative", 0),
                    "rounds": len(case_cells),
                },
                evidence_refs=tuple(sorted(set(refs))),
            )
        )
    return tuple(dimensions)


def _cap_level_insufficient(cap_id: str) -> tuple[ProfileDimension, ...]:
    return tuple(
        ProfileDimension(
            cap_id=cap_id,
            dimension=name,
            dimension_state=DimensionState.EVIDENCE_INSUFFICIENT,
            details={},
        )
        for name in ("reliability", "agent-interface")
    )


def _gateway_dimensions(
    cap_id: str, evidence: list[dict[str, Any]]
) -> tuple[ProfileDimension, ...]:
    bundles = [
        bundle
        for bundle in evidence
        if isinstance(bundle, dict)
        and isinstance(bundle.get("latency_ms"), (int, float))
        and isinstance(bundle.get("cost_credits"), (int, float))
        and bundle.get("public_digest")
    ]
    if not bundles:
        return _gateway_insufficient(cap_id)
    latency_values = sorted(float(bundle["latency_ms"]) for bundle in bundles)
    cost_values = sorted(float(bundle["cost_credits"]) for bundle in bundles)
    refs = tuple(sorted(str(bundle["public_digest"]) for bundle in bundles))
    return (
        ProfileDimension(
            cap_id=cap_id,
            dimension="latency",
            dimension_state=DimensionState.MEASURED,
            details={
                "unit": "ms",
                "measurement_boundary": "qveris_gateway",
                "cells": len(bundles),
                "min_ms": latency_values[0],
                "median_ms": _median(latency_values),
                "max_ms": latency_values[-1],
            },
            evidence_refs=refs,
        ),
        ProfileDimension(
            cap_id=cap_id,
            dimension="cost",
            dimension_state=DimensionState.MEASURED,
            details={
                "unit": "credits",
                "measurement_boundary": "qveris_gateway",
                "cells": len(bundles),
                "median_credits": round(_median(cost_values), 6),
                "total_credits": round(sum(cost_values), 6),
            },
            evidence_refs=refs,
        ),
    )


def _gateway_insufficient(cap_id: str) -> tuple[ProfileDimension, ...]:
    return tuple(
        ProfileDimension(
            cap_id=cap_id,
            dimension=name,
            dimension_state=DimensionState.EVIDENCE_INSUFFICIENT,
            details={},
        )
        for name in ("latency", "cost")
    )


def _median(values: list[float]) -> float:
    if len(values) % 2:
        return values[len(values) // 2]
    midpoint = len(values) // 2
    return (values[midpoint - 1] + values[midpoint]) / 2


def _markdown(profile: TaskFitProfile) -> str:
    lines = [
        f"# {profile.profile_id} — Task Fit Profile",
        "",
        f"- scenario: {profile.scenario_ref.scenario_id}@"
        f"{profile.scenario_ref.version}",
        f"- profile version: {profile.version}",
        "",
    ]
    by_cap: dict[str, list[ProfileDimension]] = defaultdict(list)
    for dimension in profile.cap_dimensions:
        by_cap[dimension.cap_id].append(dimension)
    for cap_id in sorted(by_cap):
        lines.append(f"## {cap_id}")
        for dimension in by_cap[cap_id]:
            state = dimension.dimension_state.value
            if dimension.evidence_refs:
                refs = f" ({len(dimension.evidence_refs)} evidence refs)"
            else:
                refs = ""
            lines.append(f"- {dimension.dimension}: {state}{refs}")
            if dimension.details:
                lines.append("  - " + json.dumps(dimension.details, sort_keys=True))
        lines.append("")
    if profile.limitations:
        lines.append("## Limitations")
        lines.extend(f"- {item}" for item in profile.limitations)
        lines.append("")
    lines.append(
        "> No provider total, ranking, or Agent-friendly composite score is included."
    )
    return "\n".join(lines) + "\n"


def _required(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise ProfileBuildError(f"{key} is required")
    return value
