from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from qveris_bench.cap_packs.stock_quote_family.publication_models import (
    StockQuoteCaseResult,
    StockQuoteSelectionRow,
    StockQuoteSelectionSnapshot,
)
from qveris_bench.models.enums import AccessPathType, CellState, RunMode
from qveris_bench.models.selection import OfficialPricingSnapshot
from qveris_bench.providers.repository import ProviderRegistryRepository
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.replay import ReleaseReplayError, replay_release_dir
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping

_CASE_ROLES: dict[str, Literal["positive", "negative_control"]] = {
    "aapl-quote": "positive",
    "invalid-stock": "negative_control",
    "aapl-freshness-precision": "positive",
    "cn-600519-market-coverage": "positive",
    "cn-600519-agent-contract": "positive",
}


class StockQuoteSelectionBuildError(ValueError):
    pass


@dataclass(frozen=True)
class StockQuoteSelectionBuild:
    snapshot: StockQuoteSelectionSnapshot
    json_bytes: bytes


def build_stock_quote_selection_snapshot(
    input_path: Path, repository_root: Path
) -> StockQuoteSelectionBuild:
    try:
        config = load_yaml_mapping(input_path)
        release_ref = _mapping(config, "release")
        release_path = repository_root / _string(release_ref, "path")
        release_bytes = release_path.read_bytes()
        actual_release_digest = release_digest(release_bytes)
        if actual_release_digest != _string(release_ref, "digest"):
            raise StockQuoteSelectionBuildError("release digest mismatch")
        replay_release_dir(release_path.parent, expected_digest=actual_release_digest)
        suite_path = repository_root / _string(config, "suite")
        cases_path = repository_root / _string(config, "cases")
        providers_root = repository_root / _string(config, "providers_root")
        suite_document = load_yaml_mapping(suite_path)
        cases_document = load_yaml_mapping(cases_path)
        release_document = json.loads(release_bytes)
    except (
        OSError,
        json.JSONDecodeError,
        ReleaseReplayError,
        YamlDocumentError,
        ValueError,
    ) as exc:
        if isinstance(exc, StockQuoteSelectionBuildError):
            raise
        raise StockQuoteSelectionBuildError(f"invalid snapshot input: {exc}") from exc

    release_metadata = _mapping(release_document, "release")
    release_fingerprint = str(release_metadata.get("suite_fingerprint"))
    if not release_fingerprint:
        raise StockQuoteSelectionBuildError("release suite fingerprint is missing")
    _validate_current_cap_inputs(suite_document, cases_document)
    github_manifest_path = release_path.with_name("github-artifacts.json")
    github_manifest = json.loads(github_manifest_path.read_bytes())
    github_run_id = str(github_manifest.get("github_run_id"))
    github_sha = str(github_manifest.get("github_sha"))
    evidence_root = repository_root / _string(config, "public_evidence_root")
    public_by_digest = _load_public_evidence(
        evidence_root, release_fingerprint, github_run_id, github_sha
    )
    cells = _list_of_mappings(release_document, "cells")
    evidence = _list_of_mappings(release_document, "evidence")
    evidence_by_run = {str(item["run_key"]): item for item in evidence}
    if len(evidence_by_run) != len(evidence) or set(evidence_by_run) != {
        str(cell["run_key"]) for cell in cells
    }:
        raise StockQuoteSelectionBuildError("release evidence topology mismatch")
    expected_public_digests = {str(item["public_digest"]) for item in evidence}
    if set(public_by_digest) != expected_public_digests:
        raise StockQuoteSelectionBuildError("public evidence topology mismatch")

    registry = {
        record.provider_id: record
        for record in ProviderRegistryRepository(providers_root).list()
    }
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for cell in cells:
        if cell.get("mode") != RunMode.DIRECT.value or not cell.get("applicable", True):
            raise StockQuoteSelectionBuildError(
                "publication requires applicable Direct cells"
            )
        identity = (str(cell["provider_id"]), str(cell["access_path_id"]))
        grouped.setdefault(identity, []).append(cell)
    display_order = tuple(tuple(item) for item in config.get("display_order", ()))
    if set(display_order) != set(grouped) or len(display_order) != len(grouped):
        raise StockQuoteSelectionBuildError(
            "display order must cover every identity once"
        )

    rows: list[StockQuoteSelectionRow] = []
    provider_digests: dict[str, str] = {}
    for provider_id, access_path_id in display_order:
        record = registry.get(str(provider_id))
        if record is None:
            raise StockQuoteSelectionBuildError("unknown Provider identity")
        access_paths = [
            path
            for path in record.access_paths
            if path.access_path_id == access_path_id
        ]
        if len(access_paths) != 1:
            raise StockQuoteSelectionBuildError("unknown Access Path identity")
        access_path = access_paths[0]
        if access_path.path_type is not AccessPathType.QVERIS_CONNECTOR:
            raise StockQuoteSelectionBuildError("tested Access Path must be QVeris")
        provider_file = providers_root / str(provider_id) / "provider.yaml"
        provider_digests[str(provider_id)] = _digest(provider_file.read_bytes())
        scoped = grouped[(str(provider_id), str(access_path_id))]
        case_results: list[StockQuoteCaseResult] = []
        for case_id, role in _CASE_ROLES.items():
            case_cells = sorted(
                (cell for cell in scoped if cell.get("case_id") == case_id),
                key=lambda item: int(item["round"]),
            )
            if len(case_cells) != 3:
                raise StockQuoteSelectionBuildError("case round topology mismatch")
            states = {str(cell["state"]) for cell in case_cells}
            if len(states) != 1 or states.pop() not in {
                CellState.COMPLETED.value,
                CellState.PROVIDER_NEGATIVE.value,
            }:
                raise StockQuoteSelectionBuildError(
                    "mixed or invalid terminal outcomes"
                )
            terminals = []
            refs = []
            for cell in case_cells:
                bundle = evidence_by_run[str(cell["run_key"])]
                public_digest = str(bundle["public_digest"])
                terminal = public_by_digest[public_digest]
                if terminal.get("run_key") != cell["run_key"] or (
                    terminal.get("outcome") != cell["state"]
                ):
                    raise StockQuoteSelectionBuildError(
                        "public terminal outcome mismatch"
                    )
                terminals.append(terminal)
                refs.append(public_digest)
            passed = sum(
                cell["state"] == CellState.COMPLETED.value for cell in case_cells
            )
            reasons = tuple(
                sorted(
                    {str(item["reason"]) for item in terminals if item.get("reason")}
                )
            )
            case_results.append(
                StockQuoteCaseResult(
                    case_id=case_id,
                    role=role,
                    state="passed"
                    if passed == len(case_cells)
                    else "provider_negative",
                    passed_rounds=passed,
                    total_rounds=len(case_cells),
                    failure_reasons=reasons,
                    evidence_refs=tuple(refs),
                )
            )
        pricing = _pricing(record.provider.official_pricing, str(access_path_id))
        rows.append(
            StockQuoteSelectionRow(
                provider_id=str(provider_id),
                provider_name=record.provider.official_name,
                access_path_id=str(access_path_id),
                access_path_type=access_path.path_type,
                case_results=tuple(case_results),
                official_pricing=pricing,
                qualified=False,
            )
        )

    snapshot = StockQuoteSelectionSnapshot(
        snapshot_id=_string(config, "snapshot_id"),
        version=_string(config, "version"),
        edition=date.fromisoformat(_string(config, "edition")),
        observation_date=date.fromisoformat(_string(config, "observation_date")),
        cap_id="stock-quote",
        release_digest=actual_release_digest,
        suite_fingerprint=release_fingerprint,
        github_run_id=github_run_id,
        github_sha=github_sha,
        input_digests={
            "selection_input": _digest(input_path.read_bytes()),
            "suite": _digest(suite_path.read_bytes()),
            "cases": _digest(cases_path.read_bytes()),
            "github_artifacts": _digest(github_manifest_path.read_bytes()),
            "public_evidence": _directory_digest(evidence_root),
            **{f"provider:{key}": value for key, value in provider_digests.items()},
        },
        rows=tuple(rows),
        limitations=tuple(
            str(item) for item in release_metadata.get("limitations", ())
        ),
    )
    json_bytes = (
        json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()
    return StockQuoteSelectionBuild(snapshot=snapshot, json_bytes=json_bytes)


def _load_public_evidence(
    root: Path, suite_fingerprint: str, github_run_id: str, github_sha: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        content = path.read_bytes()
        document = json.loads(content)
        if (
            document.get("suite_fingerprint") != suite_fingerprint
            or str(document.get("github_run_id")) != github_run_id
            or document.get("github_sha") != github_sha
            or document.get("disclosure_level") != "sanitized_public"
            or document.get("license_status") != "cleared"
        ):
            raise StockQuoteSelectionBuildError("public evidence provenance mismatch")
        digest = _digest(content)
        if digest in result:
            raise StockQuoteSelectionBuildError("duplicate public evidence digest")
        result[digest] = document
    return result


def _validate_current_cap_inputs(
    suite: dict[str, Any], cases_document: dict[str, Any]
) -> None:
    if (
        suite.get("suite_id") != "stock-quote-v3"
        or suite.get("cap_id") != "stock-quote"
        or suite.get("rounds") != 3
        or tuple(suite.get("case_ids", ())) != tuple(_CASE_ROLES)
    ):
        raise StockQuoteSelectionBuildError(
            "current Stock Quote suite topology drifted"
        )
    cases = cases_document.get("cases")
    if not isinstance(cases, list):
        raise StockQuoteSelectionBuildError("current Stock Quote cases are invalid")
    roles = {
        str(case.get("case_id")): (
            "negative_control" if case.get("negative_control") is True else "positive"
        )
        for case in cases
        if isinstance(case, dict)
    }
    if roles != _CASE_ROLES:
        raise StockQuoteSelectionBuildError("current Stock Quote case roles drifted")


def _pricing(facts: tuple[Any, ...], access_path_id: str) -> OfficialPricingSnapshot:
    matches = [
        fact
        for fact in facts
        if fact.applies_to == "provider_wide" or access_path_id in fact.applies_to
    ]
    if len(matches) != 1:
        return OfficialPricingSnapshot(state="evidence_insufficient")
    return OfficialPricingSnapshot(state="declared", **matches[0].model_dump())


def _directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.glob("*.json")):
        digest.update(item.name.encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _mapping(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise StockQuoteSelectionBuildError(f"{key} must be a mapping")
    return value


def _list_of_mappings(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise StockQuoteSelectionBuildError(f"{key} must be a list of mappings")
    return value


def _string(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise StockQuoteSelectionBuildError(f"{key} must be a string")
    return value
