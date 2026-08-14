from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from qveris_bench.models.selection import SelectionSnapshot
from qveris_bench.releases.replay import ReleaseReplayError, replay_release_dir
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping


class WriterInputBuildError(ValueError):
    pass


class EditorialValidationError(ValueError):
    pass


@dataclass(frozen=True)
class WriterInputBuild:
    json_bytes: bytes


def build_writer_input(
    selection_snapshot_path: Path,
    profile_path: Path,
    repository_root: Path,
) -> WriterInputBuild:
    try:
        snapshot = SelectionSnapshot.model_validate_json(
            selection_snapshot_path.read_bytes()
        )
        profile = load_yaml_mapping(profile_path)
    except (OSError, ValidationError, ValueError, YamlDocumentError) as exc:
        raise WriterInputBuildError(f"cannot load writer inputs: {exc}") from exc
    release_dirs = profile.get("writer_evidence_releases")
    if not isinstance(release_dirs, list) or not release_dirs:
        raise WriterInputBuildError("article profile has no writer evidence releases")
    observations: list[dict[str, Any]] = []
    release_digests: list[str] = []
    for relative in release_dirs:
        release_dir = _repository_path(repository_root, relative)
        try:
            replayed = replay_release_dir(release_dir)
        except ReleaseReplayError as exc:
            raise WriterInputBuildError(
                "writer evidence release cannot be replayed"
            ) from exc
        release_digests.append(replayed.published_digest)
        manifest = _json_document(
            release_dir / "public-evidence-manifest.json", "public evidence manifest"
        )
        entries = manifest.get("evidence")
        if not isinstance(entries, list):
            raise WriterInputBuildError("public evidence manifest has no evidence")
        for entry in entries:
            observations.append(_public_observation(repository_root, entry))
    if snapshot.market_coverage_release_digest is None:
        raise WriterInputBuildError("writer input requires a market coverage Release")
    expected_release_digests = {
        snapshot.cap_release_digest,
        snapshot.market_coverage_release_digest,
    }
    if set(release_digests) != expected_release_digests:
        raise WriterInputBuildError(
            "writer evidence releases differ from the Selection Snapshot"
        )
    rows = [row.model_dump(mode="json") for row in snapshot.rows]
    fact_catalog = _fact_catalog(snapshot)
    document = {
        "schema_version": 1,
        "cap_id": snapshot.cap_id,
        "edition": snapshot.edition.isoformat(),
        "scope": profile.get("scope"),
        "provider_count": len({row.provider_id for row in snapshot.rows}),
        "access_path_count": len(snapshot.rows),
        "live_call_count": len(observations),
        "markets": sorted(
            {
                result.market
                for row in snapshot.rows
                if row.market_coverage is not None
                for result in row.market_coverage.results
            }
        ),
        "release_digests": sorted(expected_release_digests),
        "rows": rows,
        "fact_catalog": fact_catalog,
        "public_observations": sorted(
            observations,
            key=lambda item: (
                item["provider_id"],
                item["access_path_id"],
                item["case_id"],
                item["round"],
            ),
        ),
        "editorial_contract": {
            "material_values_are_renderer_owned": True,
            "provider_identity_is_renderer_owned": True,
            "links_are_renderer_owned": True,
            "minimum_decision_scenarios": 4,
            "required_provider_analyses": [row.access_path_id for row in snapshot.rows],
        },
    }
    return WriterInputBuild(_canonical_json(document))


def load_editorial_document(path: Path, writer_input: dict[str, Any]) -> dict[str, Any]:
    document = _json_document(path, "editorial document")
    if document.get("schema_version") != 1:
        raise EditorialValidationError("unsupported editorial schema version")
    if document.get("skill_id") != "cap-article-writer":
        raise EditorialValidationError(
            "editorial document has the wrong skill identity"
        )
    if (
        not isinstance(document.get("skill_version"), str)
        or not document["skill_version"]
    ):
        raise EditorialValidationError("editorial document has no Skill version")
    catalog = writer_input.get("fact_catalog")
    if not isinstance(catalog, dict):
        raise EditorialValidationError("writer input has no fact catalog")
    blocks = _editorial_blocks(document)
    for block in blocks:
        copy = block.get("copy")
        refs = block.get("fact_refs")
        if not isinstance(copy, str) or not copy.strip():
            raise EditorialValidationError("editorial copy must be non-empty")
        if (
            not isinstance(refs, list)
            or not refs
            or not all(isinstance(ref, str) and ref in catalog for ref in refs)
        ):
            raise EditorialValidationError(
                "editorial copy has an unknown fact reference"
            )
        _validate_model_copy(copy, writer_input)
    scenarios = document.get("decision_scenarios")
    minimum = writer_input.get("editorial_contract", {}).get(
        "minimum_decision_scenarios", 4
    )
    if not isinstance(scenarios, list) or len(scenarios) < minimum:
        raise EditorialValidationError(
            "editorial document has too few decision scenarios"
        )
    path_ids = {row["access_path_id"] for row in writer_input.get("rows", [])}
    for scenario in scenarios:
        selected = scenario.get("recommended_access_path_ids")
        if (
            not isinstance(selected, list)
            or not selected
            or not set(selected) <= path_ids
        ):
            raise EditorialValidationError(
                "decision scenario has an unknown Access Path"
            )
        heading = scenario.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            raise EditorialValidationError("decision scenario has no heading")
        _validate_model_copy(heading, writer_input)
    analyses = document.get("provider_analyses")
    if (
        not isinstance(analyses, list)
        or {item.get("access_path_id") for item in analyses if isinstance(item, dict)}
        != path_ids
    ):
        raise EditorialValidationError(
            "editorial provider analyses do not match Provider × Access Path rows"
        )
    for analysis in analyses:
        path_id = analysis["access_path_id"]
        if not any(ref.startswith(f"path:{path_id}:") for ref in analysis["fact_refs"]):
            raise EditorialValidationError(
                "Provider analysis is not bound to its Access Path facts"
            )
    faq = document.get("faq")
    if not isinstance(faq, list) or len(faq) < 3:
        raise EditorialValidationError("editorial document has too few FAQ entries")
    for item in faq:
        question = item.get("question") if isinstance(item, dict) else None
        answer = item.get("answer") if isinstance(item, dict) else None
        if not isinstance(question, str) or not isinstance(answer, str):
            raise EditorialValidationError("editorial FAQ is invalid")
        refs = item.get("fact_refs")
        if (
            not isinstance(refs, list)
            or not refs
            or not all(isinstance(ref, str) and ref in catalog for ref in refs)
        ):
            raise EditorialValidationError(
                "editorial FAQ has an unknown fact reference"
            )
        _validate_model_copy(question, writer_input)
        _validate_model_copy(answer, writer_input)
    return document


def _editorial_blocks(document: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for key in (
        "lead",
        "evidence_explainer",
        "cap_explainer",
        "agent_notes",
        "limitations",
    ):
        value = document.get(key)
        if not isinstance(value, dict):
            raise EditorialValidationError(f"editorial document is missing {key}")
        blocks.append(value)
    charts = document.get("chart_explanations")
    if not isinstance(charts, dict) or set(charts) != {"market", "tradeoff"}:
        raise EditorialValidationError("editorial chart explanations are incomplete")
    blocks.extend(charts.values())
    for key in ("decision_scenarios", "provider_analyses"):
        value = document.get(key)
        if not isinstance(value, list):
            raise EditorialValidationError(f"editorial document is missing {key}")
        blocks.extend(item for item in value if isinstance(item, dict))
    return blocks


def _validate_model_copy(copy: str, writer_input: dict[str, Any]) -> None:
    if re.search(r"\d|https?://|sha256:|credits?/call", copy, re.IGNORECASE):
        raise EditorialValidationError(
            "material values and links must be rendered from deterministic facts"
        )
    provider_names = {
        str(row.get("provider_name", ""))
        for row in writer_input.get("rows", [])
        if row.get("provider_name")
    }
    if any(name.lower() in copy.lower() for name in provider_names):
        raise EditorialValidationError(
            "Provider identity must be selected structurally, not written in prose"
        )
    if re.search(r"\b(overall winner|best provider|best api)\b", copy, re.IGNORECASE):
        raise EditorialValidationError(
            "editorial copy must not declare an overall winner"
        )


def _fact_catalog(snapshot: SelectionSnapshot) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {
        "article:scope": {"kind": "scope"},
        "article:evidence-states": {"kind": "evidence_boundary"},
        "article:markets": {"kind": "market_matrix"},
        "article:runtime-tradeoff": {"kind": "latency_and_list_price"},
        "article:agent-boundary": {"kind": "agent_interface"},
        "article:limitations": {"kind": "limitations"},
        "article:no-overall-winner": {"kind": "editorial_policy"},
    }
    for row in snapshot.rows:
        prefix = f"path:{row.access_path_id}"
        catalog[f"{prefix}:list-price"] = {
            "kind": "qveris_list_price",
            "value": row.qveris_list_price.model_dump(mode="json"),
        }
        catalog[f"{prefix}:latency"] = {
            "kind": "gateway_latency",
            "value": row.gateway_metrics.model_dump(mode="json"),
        }
        catalog[f"{prefix}:market-coverage"] = {
            "kind": "market_coverage",
            "value": (
                row.market_coverage.model_dump(mode="json")
                if row.market_coverage is not None
                else None
            ),
        }
        catalog[f"{prefix}:invalid-input"] = {
            "kind": "invalid_input",
            "value": row.agent_interface.invalid_input_handling.model_dump(mode="json"),
        }
        catalog[f"{prefix}:official-pricing"] = {
            "kind": "official_pricing",
            "value": row.official_pricing.model_dump(mode="json"),
        }
        catalog[f"{prefix}:sample"] = {"kind": "public_terminal_sample"}
    return catalog


def _public_observation(repository_root: Path, entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise WriterInputBuildError("public evidence entry is invalid")
    path = _repository_path(repository_root, entry.get("path"))
    data = path.read_bytes()
    digest = _digest(data)
    if digest != entry.get("public_digest"):
        raise WriterInputBuildError("public evidence digest mismatch")
    document = _json_document(path, "public evidence")
    run_key = document.get("run_key")
    if run_key != entry.get("run_key") or not isinstance(run_key, str):
        raise WriterInputBuildError("public evidence run identity mismatch")
    parts = run_key.split(":")
    if len(parts) < 7:
        raise WriterInputBuildError("public evidence run key is invalid")
    return {
        "fact_id": f"evidence:{entry['evidence_id']}",
        "evidence_id": entry["evidence_id"],
        "public_digest": digest,
        "provider_id": document.get("provider_id"),
        "access_path_id": document.get("access_path_id"),
        "case_id": parts[2],
        "round": int(parts[-1]),
        "state": document.get("state"),
        "failure_attribution": document.get("failure_attribution"),
        "latency_ms": document.get("latency_ms"),
        "facts": document.get("facts")
        if isinstance(document.get("facts"), dict)
        else {},
        "unmet_conditions": document.get("unmet_conditions", []),
    }


def _repository_path(repository_root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise WriterInputBuildError("writer evidence path is invalid")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise WriterInputBuildError("writer evidence path is invalid")
    resolved = (repository_root / relative).resolve()
    if not resolved.is_relative_to(repository_root.resolve()):
        raise WriterInputBuildError("writer evidence path escapes repository")
    return resolved


def _json_document(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error = (
            EditorialValidationError
            if label == "editorial document"
            else WriterInputBuildError
        )
        raise error(f"invalid {label}: {exc}") from exc
    if not isinstance(document, dict):
        error = (
            EditorialValidationError
            if label == "editorial document"
            else WriterInputBuildError
        )
        raise error(f"invalid {label}")
    return document


def _canonical_json(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def _digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"
