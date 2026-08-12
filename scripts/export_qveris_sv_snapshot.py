from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import yaml

from qveris_bench.models.enums import (
    AccessPathType,
    DisclosureLevel,
    LicenseStatus,
)
from qveris_bench.models.selection import (
    ObservationWindow,
    ScopeValidationResult,
    ScopeValidationSnapshot,
)
from qveris_bench.providers.repository import ProviderRegistryRepository


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _aware_instant(value: object, *, source_timezone: str) -> datetime:
    instant = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if instant.utcoffset() is None:
        if source_timezone != "UTC":
            raise ValueError("naive QVeris SV datetime requires declared UTC source")
        instant = instant.replace(tzinfo=UTC)
    return instant.astimezone(UTC)


def _qveris_bindings(
    document: dict[str, Any],
    source_provider_ids: dict[str, str],
    providers_root: Path,
) -> dict[str, tuple[str, str, str]]:
    registry = {
        record.provider.provider_id: record
        for record in ProviderRegistryRepository(providers_root).list()
    }
    by_tool: dict[str, tuple[str, str, str]] = {}
    for binding in document.get("bindings", []):
        if binding.get("transport") != "qveris_connector":
            continue
        provider_id = str(binding["provider_id"])
        access_path_id = str(binding["access_path_id"])
        record = registry.get(provider_id)
        access_path = (
            next(
                (
                    item
                    for item in record.access_paths
                    if item.access_path_id == access_path_id
                ),
                None,
            )
            if record
            else None
        )
        if (
            access_path is None
            or access_path.path_type is not AccessPathType.QVERIS_CONNECTOR
        ):
            raise ValueError(
                "SV binding must resolve to a registered QVeris Access Path"
            )
        source_provider_id = source_provider_ids.get(provider_id)
        if not source_provider_id:
            raise ValueError("QVeris SV binding lacks a source Provider identity")
        tool_id = str(binding["tool_id"])
        identity = (provider_id, access_path_id, source_provider_id)
        previous = by_tool.setdefault(tool_id, identity)
        if previous != identity:
            raise ValueError("one QVeris tool cannot map to multiple Access Paths")
    return by_tool


def build_scope_validation_snapshot(
    source_bytes: bytes,
    bindings_bytes: bytes,
    identity_map_bytes: bytes,
    providers_root: Path,
    *,
    namespace: str,
    window_start: str,
    window_end: str,
    snapshot_id: str,
) -> ScopeValidationSnapshot:
    source = json.loads(source_bytes)
    bindings = json.loads(bindings_bytes)
    identity_map = yaml.safe_load(identity_map_bytes)
    if identity_map.get("namespace") != namespace:
        raise ValueError("QVeris SV identity map namespace mismatch")
    if source.get("capability_ids") != [namespace]:
        raise ValueError("QVeris SV source Capability does not match namespace")
    if source.get("source_conditions") != "pair_current_covered_conditions":
        raise ValueError("QVeris SV source is not the current Pair cohort")

    rows = source.get("rows")
    if not isinstance(rows, list):
        raise ValueError("QVeris SV source rows must be a list")
    actual_rows_digest = hashlib.sha256(_canonical_bytes(rows)).hexdigest()
    if source.get("rows_sha256") != actual_rows_digest:
        raise ValueError("QVeris SV source rows digest mismatch")

    source_timezone = str(identity_map.get("source_timezone", ""))
    capture = _aware_instant(
        source["snapshot_started_at"], source_timezone=source_timezone
    )
    window = ObservationWindow(
        start=date.fromisoformat(window_start), end=date.fromisoformat(window_end)
    )
    window_start_instant = datetime.combine(window.start, time.min, tzinfo=UTC)
    window_end_exclusive = datetime.combine(window.end, time.max, tzinfo=UTC)
    if not window_start_instant <= capture <= window_end_exclusive:
        raise ValueError(
            "QVeris SV capture instant falls outside the observation window"
        )

    source_provider_ids = {
        str(key): str(value)
        for key, value in identity_map.get("source_provider_ids", {}).items()
    }
    identities = _qveris_bindings(bindings, source_provider_ids, providers_root)
    selected_rows: dict[str, dict[str, Any]] = {}
    for row in rows:
        tool_id = str(row.get("tool_id", ""))
        if tool_id not in identities:
            continue
        if row.get("is_current") is False:
            raise ValueError("QVeris SV source row is not current")
        provider_id, _, expected_source_provider_id = identities[tool_id]
        if row.get("provider_id") != expected_source_provider_id:
            raise ValueError(
                f"source Provider does not match binding Provider {provider_id}"
            )
        if row.get("capability_id") != namespace:
            raise ValueError("source Capability does not match QVeris SV namespace")
        if tool_id in selected_rows:
            raise ValueError("QVeris SV source contains duplicate current tool rows")
        selected_rows[tool_id] = row

    source_digest = _digest_bytes(source_bytes)
    bindings_digest = _digest_bytes(bindings_bytes)
    identity_map_digest = _digest_bytes(identity_map_bytes)
    results: list[ScopeValidationResult] = []
    suite_inputs: list[dict[str, Any]] = []
    for tool_id, row in sorted(selected_rows.items()):
        provider_id, access_path_id, _ = identities[tool_id]
        evaluated_at = _aware_instant(
            row["evaluated_at"], source_timezone=source_timezone
        )
        if not window_start_instant <= evaluated_at <= window_end_exclusive:
            raise ValueError(
                "QVeris SV evaluation falls outside the observation window"
            )
        if evaluated_at > capture:
            raise ValueError("QVeris SV evaluation occurs after source capture")
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
            if verdict.get("supported", True) is not True:
                raise ValueError("verified verdict cannot declare supported=false")
            verified_at = verdict.get("verified_at")
            if not verified_at:
                raise ValueError("verified QVeris SV market requires verified_at")
            verified_date = date.fromisoformat(str(verified_at))
            if not window.start <= verified_date <= window.end:
                raise ValueError(
                    "verified QVeris SV market falls outside the observation window"
                )
            if verified_date > capture.date():
                raise ValueError(
                    "verified QVeris SV market occurs after source capture"
                )
            evidence_payload = {
                "namespace": namespace,
                "source_snapshot_digest": source_digest,
                "source_rows_digest": "sha256:" + actual_rows_digest,
                "source_provider_id": row["provider_id"],
                "source_tool_id": tool_id,
                "evaluated_at": evaluated_at.isoformat(),
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
            "source_rows_digest": actual_rows_digest,
            "bindings_digest": bindings_digest,
            "identity_map_digest": identity_map_digest,
            "bindings": suite_inputs,
            "extractor_version": "1.1.0",
        }
    )
    return ScopeValidationSnapshot(
        snapshot_id=snapshot_id,
        version="1.0.0",
        namespace=namespace,
        observation_window=window,
        suite_fingerprint=suite_fingerprint,
        extractor_version="1.1.0",
        source_snapshot_digest=source_digest,
        source_rows_digest="sha256:" + actual_rows_digest,
        bindings_digest=bindings_digest,
        identity_map_digest=identity_map_digest,
        source_snapshot_captured_at=capture,
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
    parser.add_argument("--identity-map", type=Path, required=True)
    parser.add_argument("--providers-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--snapshot-id", required=True)
    args = parser.parse_args()

    snapshot = build_scope_validation_snapshot(
        args.source.read_bytes(),
        args.bindings.read_bytes(),
        args.identity_map.read_bytes(),
        args.providers_root,
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
