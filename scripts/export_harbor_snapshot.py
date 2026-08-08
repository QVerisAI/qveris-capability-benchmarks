#!/usr/bin/env python3
"""Offline export of Harbor symbol and coverage reference data.

Reads a local quaestio-harbor checkout's data files, normalizes selected rows into
the benchmark-owned harbor-symbol-registry schema, validates the snapshot, and
writes it to a private output directory. The artifact is private operator data: it
must not be committed to the public repository. Public releases reference only the
printed SHA-256 digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import yaml

_SCHEMA_PATH = Path(__file__).resolve().parent / "harbor-symbol-registry.schema.json"
_SCHEMA_VERSION = "1.0.0"
_EXPORT_SCRIPT = "scripts/export_harbor_snapshot.py"
_LICENSE_NOTE = (
    "Private operator data derived from quaestio-harbor; do not commit to a "
    "public repository or redistribute."
)

_INPUT_PATHS = {
    "markets": "data/market-representative-tickers.yaml",
    "provider_symbol_samples": "data/audit/seed_provider_test_symbols.yaml",
    "market_anchors": "data/audit/market_anchors.yaml",
}


class _StringScalarLoader(yaml.SafeLoader):
    """SafeLoader that keeps every scalar as str.

    YAML 1.1 coerces market codes such as NO or ON to booleans; treating all
    scalars as strings preserves the operator data verbatim.
    """


def _construct_str(loader: _StringScalarLoader, node: yaml.ScalarNode) -> str:
    return loader.construct_scalar(node)


for _scalar_tag in (
    "tag:yaml.org,2002:str",
    "tag:yaml.org,2002:bool",
    "tag:yaml.org,2002:int",
    "tag:yaml.org,2002:float",
    "tag:yaml.org,2002:null",
):
    _StringScalarLoader.add_constructor(
        _scalar_tag,
        _construct_str,
    )


def _harbor_commit(harbor_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=harbor_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_StringScalarLoader)


def _normalize_markets(document: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"market": market, "representative_ticker": ticker}
        for market, ticker in sorted(document.items())
        if isinstance(market, str) and isinstance(ticker, str)
    ]


def _normalize_provider_symbol_samples(
    document: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in document.get("entries", []):
        row = {
            "provider_id": str(entry["provider_id"]),
            "market": str(entry["market"]),
            "symbol": str(entry["symbol"]),
        }
        for field in ("source", "verified_at"):
            if entry.get(field):
                row[field] = str(entry[field])
        rows.append(row)
    return sorted(
        rows, key=lambda item: (item["provider_id"], item["market"], item["symbol"])
    )


def _normalize_market_anchors(
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in document.get("markets", []):
        rows.append(
            {
                "market": str(entry["market"]),
                "company_key": str(entry["company_key"]),
                "display_name": str(entry["display_name"]),
                "candidate_tickers": [
                    str(ticker) for ticker in entry.get("candidate_tickers", [])
                ],
            }
        )
    return sorted(rows, key=lambda item: (item["market"], item["company_key"]))


def _normalize_identifier_samples(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        raise ValueError("identifier samples input must be a YAML mapping")
    entries = document.get("entries") or document.get("identifier_samples") or []
    rows: list[dict[str, Any]] = []
    for entry in entries:
        rows.append(
            {
                "market": str(entry["market"]),
                "company_key": str(entry["company_key"]),
                "identifiers": {
                    str(key): str(value)
                    for key, value in entry.get("identifiers", {}).items()
                },
            }
        )
    return sorted(rows, key=lambda item: (item["market"], item["company_key"]))


def _schema() -> Any:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def build_snapshot(
    harbor_root: Path,
    identifier_samples_path: Path | None = None,
    harbor_commit: str | None = None,
    exported_at: str | None = None,
) -> dict[str, Any]:
    """Normalize Harbor data files into the private symbol registry snapshot."""
    inputs = list(_INPUT_PATHS.values())
    markets = _normalize_markets(_load_yaml(harbor_root / _INPUT_PATHS["markets"]))
    provider_symbol_samples = _normalize_provider_symbol_samples(
        _load_yaml(harbor_root / _INPUT_PATHS["provider_symbol_samples"])
    )
    market_anchors = _normalize_market_anchors(
        _load_yaml(harbor_root / _INPUT_PATHS["market_anchors"])
    )
    identifier_samples: list[dict[str, Any]] = []
    if identifier_samples_path is not None:
        identifier_samples = _normalize_identifier_samples(
            _load_yaml(identifier_samples_path)
        )
        inputs.append(str(identifier_samples_path))
    commit = harbor_commit or _harbor_commit(harbor_root)
    snapshot = {
        "schema_version": _SCHEMA_VERSION,
        "provenance": {
            "source": "quaestio-harbor",
            "harbor_commit": commit,
            "exported_at": exported_at
            or datetime.now(UTC).isoformat(timespec="seconds"),
            "export_script": _EXPORT_SCRIPT,
            "inputs": sorted(inputs),
            "license_note": _LICENSE_NOTE,
        },
        "markets": markets,
        "provider_symbol_samples": provider_symbol_samples,
        "market_anchors": market_anchors,
        "identifier_samples": identifier_samples,
    }
    jsonschema.validate(snapshot, _schema())
    return snapshot


def _canonical_bytes(snapshot: dict[str, Any]) -> bytes:
    return (json.dumps(snapshot, indent=2, sort_keys=True) + "\n").encode()


def export_snapshot(
    harbor_root: Path,
    output_dir: Path,
    identifier_samples_path: Path | None = None,
    harbor_commit: str | None = None,
    exported_at: str | None = None,
) -> dict[str, Any]:
    """Write the snapshot plus a manifest and return the manifest."""
    snapshot = build_snapshot(
        harbor_root,
        identifier_samples_path=identifier_samples_path,
        harbor_commit=harbor_commit,
        exported_at=exported_at,
    )
    content = _canonical_bytes(snapshot)
    digest = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / f"harbor-symbol-registry-{digest[:8]}.json"
    snapshot_path.write_bytes(content)
    manifest = {
        "snapshot_file": snapshot_path.name,
        "sha256": digest,
        "exported_at": snapshot["provenance"]["exported_at"],
        "inputs": snapshot["provenance"]["inputs"],
        "counts": {
            "markets": len(snapshot["markets"]),
            "provider_symbol_samples": len(snapshot["provider_symbol_samples"]),
            "market_anchors": len(snapshot["market_anchors"]),
            "identifier_samples": len(snapshot["identifier_samples"]),
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harbor-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(".harbor-snapshots"))
    parser.add_argument("--identifier-samples", type=Path, default=None)
    parser.add_argument("--harbor-commit", type=str, default=None)
    args = parser.parse_args()
    manifest = export_snapshot(
        args.harbor_root,
        args.output_dir,
        identifier_samples_path=args.identifier_samples,
        harbor_commit=args.harbor_commit,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
