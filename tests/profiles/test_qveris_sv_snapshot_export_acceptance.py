from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.export_qveris_sv_snapshot import build_scope_validation_snapshot

ROOT = Path(__file__).resolve().parents[2]


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def _identity_bytes() -> bytes:
    return b"""schema_version: 1
namespace: MKT.DIVIDENDS
source_provider_ids:
  eodhd: eodhd
"""


def test_ac1_export_keeps_only_verified_markets_for_bound_qveris_tools() -> None:
    source = {
        "snapshot_started_at": "2026-08-12T01:53:36+00:00",
        "capability_ids": ["MKT.DIVIDENDS"],
        "source_conditions": "pair_current_covered_conditions",
        "rows": [
            {
                "provider_id": "eodhd",
                "capability_id": "MKT.DIVIDENDS",
                "tool_id": "eodhd.dividends",
                "evaluated_at": "2026-07-20T11:19:25+00:00",
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
                "capability_id": "MKT.DIVIDENDS",
                "tool_id": "unrelated.dividends",
                "evaluated_at": "2026-07-20T11:19:25+00:00",
                "scope_snapshot": {
                    "markets": {"JP": {"status": "verified"}},
                },
            },
        ],
    }
    source["rows_sha256"] = hashlib.sha256(
        json.dumps(
            source["rows"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
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
    source_bytes = _bytes(source)
    binding_bytes = _bytes(bindings)

    snapshot = build_scope_validation_snapshot(
        source_bytes,
        binding_bytes,
        _identity_bytes(),
        ROOT / "providers",
        namespace="MKT.DIVIDENDS",
        window_start="2026-07-20",
        window_end="2026-08-12",
        snapshot_id="qveris-dividend-sv-2026-q3-v1",
    )

    assert snapshot.source_snapshot_captured_at.isoformat() == (
        "2026-08-12T01:53:36+00:00"
    )
    assert snapshot.source_snapshot_digest.startswith("sha256:")
    assert snapshot.source_rows_digest == "sha256:" + source["rows_sha256"]
    assert snapshot.bindings_digest == (
        "sha256:" + hashlib.sha256(binding_bytes).hexdigest()
    )
    assert snapshot.identity_map_digest.startswith("sha256:")
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
        "capability_ids": ["MKT.DIVIDENDS"],
        "source_conditions": "pair_current_covered_conditions",
        "rows_sha256": hashlib.sha256(b"[]").hexdigest(),
        "rows": [],
    }
    bindings = {"bindings": []}
    kwargs = {
        "namespace": "MKT.DIVIDENDS",
        "window_start": "2026-07-20",
        "window_end": "2026-08-12",
        "snapshot_id": "qveris-dividend-sv-2026-q3-v1",
    }

    first = build_scope_validation_snapshot(
        _bytes(source),
        _bytes(bindings),
        _identity_bytes(),
        ROOT / "providers",
        **kwargs,
    )
    second = build_scope_validation_snapshot(
        _bytes(source),
        _bytes(bindings),
        _identity_bytes(),
        ROOT / "providers",
        **kwargs,
    )

    assert first.model_dump_json() == second.model_dump_json()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"provider_id": "hangseng_polysource"}, "source Provider"),
        ({"capability_id": "MKT.UNRELATED"}, "source Capability"),
        ({"is_current": False}, "current"),
    ],
)
def test_ac3_export_rejects_wrong_or_stale_source_identity(
    mutation: dict[str, object], message: str
) -> None:
    row = {
        "provider_id": "eodhd",
        "capability_id": "MKT.DIVIDENDS",
        "tool_id": "eodhd.dividends",
        "evaluated_at": "2026-07-20T11:19:25+00:00",
        "scope_snapshot": {
            "markets": {"US": {"status": "verified", "verified_at": "2026-07-20"}}
        },
        **mutation,
    }
    source = {
        "snapshot_started_at": "2026-08-12T01:53:36+00:00",
        "capability_ids": ["MKT.DIVIDENDS"],
        "source_conditions": "pair_current_covered_conditions",
        "rows": [row],
    }
    source["rows_sha256"] = hashlib.sha256(
        json.dumps(source["rows"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    bindings = {
        "bindings": [
            {
                "provider_id": "eodhd",
                "access_path_id": "eodhd-dividends-qveris",
                "transport": "qveris_connector",
                "tool_id": "eodhd.dividends",
            }
        ]
    }

    with pytest.raises(ValueError, match=message):
        build_scope_validation_snapshot(
            _bytes(source),
            _bytes(bindings),
            _identity_bytes(),
            ROOT / "providers",
            namespace="MKT.DIVIDENDS",
            window_start="2026-07-20",
            window_end="2026-08-12",
            snapshot_id="qveris-dividend-sv-2026-q3-v1",
        )


def test_ac4_export_rejects_false_verified_and_forged_rows_digest() -> None:
    row = {
        "provider_id": "eodhd",
        "capability_id": "MKT.DIVIDENDS",
        "tool_id": "eodhd.dividends",
        "evaluated_at": "2026-07-20T11:19:25+00:00",
        "scope_snapshot": {
            "markets": {
                "US": {
                    "status": "verified",
                    "supported": False,
                    "verified_at": "2026-07-20",
                }
            }
        },
    }
    source = {
        "snapshot_started_at": "2026-08-12T01:53:36+00:00",
        "capability_ids": ["MKT.DIVIDENDS"],
        "source_conditions": "pair_current_covered_conditions",
        "rows_sha256": "f" * 64,
        "rows": [row],
    }
    bindings = {
        "bindings": [
            {
                "provider_id": "eodhd",
                "access_path_id": "eodhd-dividends-qveris",
                "transport": "qveris_connector",
                "tool_id": "eodhd.dividends",
            }
        ]
    }

    with pytest.raises(ValueError, match="rows digest"):
        build_scope_validation_snapshot(
            _bytes(source),
            _bytes(bindings),
            _identity_bytes(),
            ROOT / "providers",
            namespace="MKT.DIVIDENDS",
            window_start="2026-07-20",
            window_end="2026-08-12",
            snapshot_id="qveris-dividend-sv-2026-q3-v1",
        )

    source["rows_sha256"] = hashlib.sha256(
        json.dumps(source["rows"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="verified verdict"):
        build_scope_validation_snapshot(
            _bytes(source),
            _bytes(bindings),
            _identity_bytes(),
            ROOT / "providers",
            namespace="MKT.DIVIDENDS",
            window_start="2026-07-20",
            window_end="2026-08-12",
            snapshot_id="qveris-dividend-sv-2026-q3-v1",
        )


def test_ac5_export_normalizes_instants_to_utc_and_rejects_future_capture() -> None:
    source = {
        "snapshot_started_at": "2026-08-12T23:30:00-12:00",
        "capability_ids": ["MKT.DIVIDENDS"],
        "source_conditions": "pair_current_covered_conditions",
        "rows_sha256": hashlib.sha256(b"[]").hexdigest(),
        "rows": [],
    }

    with pytest.raises(ValueError, match="capture instant"):
        build_scope_validation_snapshot(
            _bytes(source),
            b'{"bindings": []}\n',
            _identity_bytes(),
            ROOT / "providers",
            namespace="MKT.DIVIDENDS",
            window_start="2026-07-20",
            window_end="2026-08-12",
            snapshot_id="qveris-dividend-sv-2026-q3-v1",
        )
