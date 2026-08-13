#!/usr/bin/env python3
"""Offline export of Harbor explore v2 catalog and per-CAP contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

_DEFAULT_BASE_URL = "https://harbor.qveris.cloud"
_KEY_ENV = "QVERIS_HARBOR_EXPLORE_KEY"
_TIMEOUT_SECONDS = 30
_EXPORTER_VERSION = "1.0.0"


def build_contract_url(base_url: str, capability_id: str) -> str:
    quoted = urllib.parse.quote(capability_id, safe=".-")
    return f"{base_url}/api/v2/explore/capabilities/{quoted}/contract"


def fetch_json(url: str, key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"X-API-Key": key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GET {url} -> HTTP {exc.code}") from exc


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )


def _canonical_records(records: object) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise RuntimeError("Harbor contracts must be a list")
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("Harbor contract record must be an object")
        capability_id = record.get("capability_id")
        contract = record.get("contract")
        if not isinstance(capability_id, str) or not isinstance(contract, dict):
            raise RuntimeError("Harbor contract record is incomplete")
        if contract.get("capability_id") != capability_id:
            raise RuntimeError("Harbor contract identity does not match its record")
        normalized.append({"capability_id": capability_id, "contract": contract})
    return sorted(normalized, key=lambda record: record["capability_id"])


def _canonical_catalog(catalog: object) -> dict[str, Any]:
    if not isinstance(catalog, dict) or not isinstance(catalog.get("items"), list):
        raise RuntimeError("Harbor catalog must contain an item list")
    items = catalog["items"]
    if not all(
        isinstance(item, dict) and isinstance(item.get("capability_id"), str)
        for item in items
    ):
        raise RuntimeError("Harbor catalog item is incomplete")
    return {**catalog, "items": sorted(items, key=lambda item: item["capability_id"])}


def _write_catalog(out_dir: Path, catalog: object, records: object) -> dict[str, Any]:
    canonical_catalog = _canonical_catalog(catalog)
    contracts = _canonical_records(records)
    catalog_bytes = _canonical_json(canonical_catalog)
    contracts_bytes = _canonical_json(contracts)
    catalog_snapshot_digest = hashlib.sha256(contracts_bytes).hexdigest()
    contract_provenance = [
        {
            "capability_id": record["capability_id"],
            "contract_version": record["contract"].get("contract_version"),
            "contract_digest": hashlib.sha256(
                json.dumps(
                    record["contract"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        }
        for record in contracts
    ]
    metadata = {
        "origin": _DEFAULT_BASE_URL,
        "exporter_version": _EXPORTER_VERSION,
        "counts": {
            "catalog": len(canonical_catalog["items"]),
            "contracts": len(contracts),
            "errors": 0,
        },
        "catalog_snapshot_digest": catalog_snapshot_digest,
        "contracts": contract_provenance,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "catalog.json").write_bytes(catalog_bytes)
    (out_dir / "contracts.json").write_bytes(contracts_bytes)
    (out_dir / "meta.json").write_bytes(_canonical_json(metadata))
    return {
        "counts": metadata["counts"],
        "digest": catalog_snapshot_digest,
        "output_dir": str(out_dir),
    }


def normalize_catalog(out_dir: Path) -> dict[str, Any]:
    try:
        catalog = json.loads((out_dir / "catalog.json").read_bytes())
        contracts = json.loads((out_dir / "contracts.json").read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Harbor catalog directory is unreadable") from exc
    return _write_catalog(out_dir, catalog, contracts)


def export_catalog(
    base_url: str,
    key: str,
    out_dir: Path,
    fetch: Callable[[str, str], dict[str, Any]] = fetch_json,
) -> dict[str, Any]:
    catalog = fetch(f"{base_url}/api/v2/explore/catalog", key)
    items = catalog.get("items", [])
    contracts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for item in items:
        capability_id = item["capability_id"]
        url = build_contract_url(base_url, capability_id)
        try:
            contracts.append(
                {"capability_id": capability_id, "contract": fetch(url, key)}
            )
        except RuntimeError as exc:
            errors.append({"capability_id": capability_id, "error": str(exc)})

    if errors:
        raise RuntimeError("Harbor catalog export is incomplete")
    return _write_catalog(out_dir, catalog, contracts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("harbor_catalog"),
        help="Versioned public catalog directory.",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Rebuild deterministic metadata from an existing catalog directory.",
    )
    args = parser.parse_args(argv)

    if args.normalize:
        result = normalize_catalog(args.output)
        print(
            f"normalized catalog={result['counts']['catalog']} "
            f"contracts={result['counts']['contracts']} digest={result['digest']}"
        )
        return 0

    key = os.getenv(_KEY_ENV)
    if not key:
        print(
            f"{_KEY_ENV} is required; set it via a local env file or GitHub secret.",
            file=sys.stderr,
        )
        return 2

    result = export_catalog(_DEFAULT_BASE_URL, key, args.output)
    print(
        f"exported catalog={result['counts']['catalog']} "
        f"contracts={result['counts']['contracts']} "
        f"errors={result['counts']['errors']} digest={result['digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
