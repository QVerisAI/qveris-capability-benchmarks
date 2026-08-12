from __future__ import annotations

import hashlib
import json

from scripts.export_qveris_sv_snapshot import build_scope_validation_snapshot


def test_ac1_export_keeps_only_verified_markets_for_bound_qveris_tools() -> None:
    source = {
        "snapshot_started_at": "2026-08-12T01:53:36+00:00",
        "rows_sha256": "a" * 64,
        "rows": [
            {
                "provider_id": "eodhd",
                "tool_id": "eodhd.dividends",
                "evaluated_at": "2026-07-20 11:19:25",
                "scope_snapshot": {
                    "probe_contract_fingerprint": "b" * 64,
                    "markets": {
                        "US": {"status": "verified", "verified_at": "2026-07-20"},
                        "CN": {"status": "unresolved", "error": "empty_result"},
                    },
                },
            },
            {
                "provider_id": "unrelated",
                "tool_id": "unrelated.dividends",
                "evaluated_at": "2026-07-20 11:19:25",
                "scope_snapshot": {
                    "markets": {"JP": {"status": "verified"}},
                },
            },
        ],
    }
    bindings = {
        "bindings": [
            {
                "binding_id": "eodhd-positive",
                "provider_id": "eodhd",
                "access_path_id": "eodhd-dividends-qveris",
                "transport": "qveris_connector",
                "tool_id": "eodhd.dividends",
            },
            {
                "binding_id": "eodhd-negative",
                "provider_id": "eodhd",
                "access_path_id": "eodhd-dividends-qveris",
                "transport": "qveris_connector",
                "tool_id": "eodhd.dividends",
            },
            {
                "binding_id": "native",
                "provider_id": "ifind",
                "access_path_id": "ifind-native-mcp",
                "transport": "native_mcp",
                "tool_id": "ifind.dividends",
            },
        ]
    }
    source_bytes = (json.dumps(source, sort_keys=True) + "\n").encode()

    snapshot = build_scope_validation_snapshot(
        source,
        bindings,
        source_snapshot_digest="sha256:" + hashlib.sha256(source_bytes).hexdigest(),
        namespace="MKT.DIVIDENDS",
        window_start="2026-07-20",
        window_end="2026-08-12",
        snapshot_id="qveris-dividend-sv-2026-q3-v1",
    )

    assert snapshot.source_snapshot_captured_at.isoformat() == (
        "2026-08-12T01:53:36+00:00"
    )
    assert snapshot.source_snapshot_digest.startswith("sha256:")
    assert snapshot.suite_fingerprint != source["rows_sha256"]
    assert [result.model_dump(mode="json") for result in snapshot.results] == [
        {
            "provider_id": "eodhd",
            "access_path_id": "eodhd-dividends-qveris",
            "market": "US",
            "supported": True,
            "evidence_ref": snapshot.results[0].evidence_ref,
        }
    ]
    assert snapshot.results[0].evidence_ref.startswith("sha256:")


def test_ac2_export_is_deterministic() -> None:
    source = {
        "snapshot_started_at": "2026-08-12T01:53:36+00:00",
        "rows_sha256": "a" * 64,
        "rows": [],
    }
    bindings = {"bindings": []}
    kwargs = {
        "source_snapshot_digest": "sha256:" + "c" * 64,
        "namespace": "MKT.DIVIDENDS",
        "window_start": "2026-07-20",
        "window_end": "2026-08-12",
        "snapshot_id": "qveris-dividend-sv-2026-q3-v1",
    }

    first = build_scope_validation_snapshot(source, bindings, **kwargs)
    second = build_scope_validation_snapshot(source, bindings, **kwargs)

    assert first.model_dump_json() == second.model_dump_json()
