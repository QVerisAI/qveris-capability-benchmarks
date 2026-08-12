from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from qveris_bench.models.enums import DisclosureLevel, LicenseStatus
from qveris_bench.models.selection import (
    ObservationWindow,
    ScopeValidationResult,
    ScopeValidationSnapshot,
)


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _qveris_bindings(document: dict[str, Any]) -> dict[str, tuple[str, str]]:
    by_tool: dict[str, tuple[str, str]] = {}
    for binding in document.get("bindings", []):
        if binding.get("transport") != "qveris_connector":
            continue
        tool_id = str(binding["tool_id"])
        identity = (str(binding["provider_id"]), str(binding["access_path_id"]))
        previous = by_tool.setdefault(tool_id, identity)
        if previous != identity:
            raise ValueError("one QVeris tool cannot map to multiple Access Paths")
    return by_tool


def build_scope_validation_snapshot(
    source: dict[str, Any],
    bindings: dict[str, Any],
    *,
    source_snapshot_digest: str,
    namespace: str,
    window_start: str,
    window_end: str,
    snapshot_id: str,
) -> ScopeValidationSnapshot:
    window = ObservationWindow(
        start=date.fromisoformat(window_start), end=date.fromisoformat(window_end)
    )
    identities = _qveris_bindings(bindings)
    selected_rows: dict[str, dict[str, Any]] = {}
    for row in source.get("rows", []):
        tool_id = str(row.get("tool_id", ""))
        if tool_id not in identities:
            continue
        if tool_id in selected_rows:
            raise ValueError("QVeris SV source contains duplicate current tool rows")
        selected_rows[tool_id] = row

    results: list[ScopeValidationResult] = []
    suite_inputs: list[dict[str, Any]] = []
    for tool_id, row in sorted(selected_rows.items()):
        provider_id, access_path_id = identities[tool_id]
        evaluated_at = datetime.fromisoformat(str(row["evaluated_at"]))
        if not window.start <= evaluated_at.date() <= window.end:
            raise ValueError(
                "QVeris SV evaluation falls outside the observation window"
            )
        scope = row.get("scope_snapshot") or {}
        suite_inputs.append(
            {
                "provider_id": provider_id,
                "access_path_id": access_path_id,
                "tool_id": tool_id,
                "probe_contract_fingerprint": scope.get("probe_contract_fingerprint"),
            }
        )
        for market, verdict in sorted((scope.get("markets") or {}).items()):
            if verdict.get("status") != "verified":
                continue
            verified_at = verdict.get("verified_at")
            if not verified_at:
                raise ValueError("verified QVeris SV market requires verified_at")
            verified_date = date.fromisoformat(str(verified_at))
            if not window.start <= verified_date <= window.end:
                raise ValueError(
                    "verified QVeris SV market falls outside the observation window"
                )
            evidence_payload = {
                "namespace": namespace,
                "source_snapshot_digest": source_snapshot_digest,
                "source_rows_sha256": source["rows_sha256"],
                "source_provider_id": row.get("provider_id"),
                "source_tool_id": tool_id,
                "evaluated_at": str(row["evaluated_at"]),
                "provider_id": provider_id,
                "access_path_id": access_path_id,
                "market": market,
                "verdict": verdict,
            }
            results.append(
                ScopeValidationResult(
                    provider_id=provider_id,
                    access_path_id=access_path_id,
                    market=str(market),
                    supported=True,
                    evidence_ref="sha256:" + _canonical_digest(evidence_payload),
                )
            )

    suite_fingerprint = _canonical_digest(
        {
            "namespace": namespace,
            "source_rows_sha256": source["rows_sha256"],
            "bindings": suite_inputs,
            "extractor_version": "1.0.0",
        }
    )
    return ScopeValidationSnapshot(
        snapshot_id=snapshot_id,
        version="1.0.0",
        namespace=namespace,
        observation_window=window,
        suite_fingerprint=suite_fingerprint,
        extractor_version="1.0.0",
        source_snapshot_digest=source_snapshot_digest,
        source_snapshot_captured_at=datetime.fromisoformat(
            source["snapshot_started_at"]
        ),
        disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
        license_status=LicenseStatus.CLEARED,
        results=tuple(
            sorted(
                results,
                key=lambda item: (item.provider_id, item.access_path_id, item.market),
            )
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--snapshot-id", required=True)
    args = parser.parse_args()

    source_bytes = args.source.read_bytes()
    snapshot = build_scope_validation_snapshot(
        json.loads(source_bytes),
        json.loads(args.bindings.read_bytes()),
        source_snapshot_digest="sha256:" + hashlib.sha256(source_bytes).hexdigest(),
        namespace=args.namespace,
        window_start=args.window_start,
        window_end=args.window_end,
        snapshot_id=args.snapshot_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
