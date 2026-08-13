from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from qveris_bench.models.cap import SourceReference

_HARBOR_EXPLORE_ORIGIN = "https://harbor.qveris.cloud"


class HarborSnapshotError(ValueError):
    pass


def canonical_contract_digest(contract: object) -> str:
    return hashlib.sha256(
        json.dumps(
            contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def load_public_harbor_contracts(
    contracts_path: Path | None,
) -> dict[str, dict[str, Any]]:
    if contracts_path is None:
        raise HarborSnapshotError("Harbor contract snapshot is required")
    try:
        payload = contracts_path.read_bytes()
        records = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise HarborSnapshotError("Harbor contract snapshot is unreadable") from exc
    if not isinstance(records, list):
        raise HarborSnapshotError(
            "Harbor contract snapshot must contain a contract list"
        )
    _validate_snapshot_metadata(contracts_path, payload)
    if any(
        record["contract"].get("capability_id") != record["capability_id"]
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("capability_id"), str)
        and isinstance(record.get("contract"), dict)
    ):
        raise HarborSnapshotError("Harbor contract identity does not match its record")
    index = {
        record["capability_id"]: record["contract"]
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("capability_id"), str)
        and isinstance(record.get("contract"), dict)
    }
    if len(index) != len(records):
        raise HarborSnapshotError("Harbor contract snapshot contains invalid records")
    return index


def validate_harbor_source(
    source: SourceReference, contracts_path: Path | None
) -> None:
    index = load_public_harbor_contracts(contracts_path)
    assert contracts_path is not None
    payload = contracts_path.read_bytes()
    snapshot_digest = hashlib.sha256(payload).hexdigest()
    if snapshot_digest != source.catalog_snapshot_digest:
        raise HarborSnapshotError(
            "Harbor contract snapshot digest does not match CAP provenance"
        )
    contract = index.get(source.harbor_capability_id)
    if contract is None:
        raise HarborSnapshotError(
            "Harbor contract snapshot must contain exactly one CAP contract"
        )
    if contract.get("capability_id") != source.harbor_capability_id:
        raise HarborSnapshotError("Harbor contract identity does not match its record")
    if contract.get("contract_version") != source.contract_version:
        raise HarborSnapshotError(
            "Harbor contract version does not match CAP provenance"
        )
    if canonical_contract_digest(contract) != source.contract_digest:
        raise HarborSnapshotError(
            "Harbor contract digest does not match CAP provenance"
        )


def _validate_snapshot_metadata(contracts_path: Path, payload: bytes) -> None:
    try:
        metadata = json.loads(contracts_path.with_name("meta.json").read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise HarborSnapshotError(
            "Harbor contract snapshot metadata is unreadable"
        ) from exc
    if not isinstance(metadata, dict):
        raise HarborSnapshotError("Harbor contract snapshot metadata must be an object")
    if metadata.get("origin") != _HARBOR_EXPLORE_ORIGIN:
        raise HarborSnapshotError("Harbor contract snapshot has an untrusted origin")
    if metadata.get("exporter_version") != "1.0.0":
        raise HarborSnapshotError("Harbor contract snapshot exporter is unsupported")
    if metadata.get("catalog_snapshot_digest") != hashlib.sha256(payload).hexdigest():
        raise HarborSnapshotError("Harbor contract snapshot metadata digest is invalid")
    contracts = metadata.get("contracts")
    if not isinstance(contracts, list):
        raise HarborSnapshotError("Harbor contract provenance metadata is missing")
    try:
        records = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HarborSnapshotError("Harbor contract snapshot is unreadable") from exc
    expected = [
        {
            "capability_id": record["capability_id"],
            "contract_version": record["contract"].get("contract_version"),
            "contract_digest": canonical_contract_digest(record["contract"]),
        }
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("capability_id"), str)
        and isinstance(record.get("contract"), dict)
    ]
    if contracts != expected:
        raise HarborSnapshotError(
            "Harbor contract provenance metadata does not match contracts"
        )
    try:
        catalog = json.loads(contracts_path.with_name("catalog.json").read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise HarborSnapshotError("Harbor catalog snapshot is unreadable") from exc
    catalog_items = catalog.get("items") if isinstance(catalog, dict) else None
    if not isinstance(catalog_items, list):
        raise HarborSnapshotError("Harbor catalog snapshot must contain an item list")
    catalog_ids = [
        item.get("capability_id")
        for item in catalog_items
        if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
    ]
    contract_ids = [record["capability_id"] for record in expected]
    if (
        len(catalog_ids) != len(catalog_items)
        or len(catalog_ids) != len(set(catalog_ids))
        or len(contract_ids) != len(set(contract_ids))
        or set(catalog_ids) != set(contract_ids)
    ):
        raise HarborSnapshotError("Harbor catalog and contracts membership differs")
