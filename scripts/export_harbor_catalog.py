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
from datetime import UTC, datetime
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


def export_catalog(
    base_url: str,
    key: str,
    out_dir: Path,
    fetch: Callable[[str, str], dict[str, Any]] = fetch_json,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
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

    counts = {
        "catalog": len(items),
        "contracts": len(contracts),
        "errors": len(errors),
    }
    if errors:
        raise RuntimeError("Harbor catalog export is incomplete")
    exported_at = datetime.now(UTC).isoformat()
    contracts_bytes = json.dumps(contracts, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
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
    (out_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "contracts.json").write_bytes(contracts_bytes)
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "exported_at": exported_at,
                "origin": _DEFAULT_BASE_URL,
                "exporter_version": _EXPORTER_VERSION,
                "counts": counts,
                "catalog_snapshot_digest": catalog_snapshot_digest,
                "contracts": contract_provenance,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "counts": counts,
        "digest": catalog_snapshot_digest,
        "output_dir": str(out_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".harbor-snapshots/catalog"),
        help="Private output directory (must stay gitignored)",
    )
    args = parser.parse_args(argv)

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
