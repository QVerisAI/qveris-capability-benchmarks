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


def validate_harbor_source(
    source: SourceReference, contracts_path: Path | None
) -> None:
    if contracts_path is None:
        raise HarborSnapshotError(
            "Harbor contract snapshot is required to freeze a formal CAP"
        )
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
    snapshot_digest = hashlib.sha256(payload).hexdigest()
    if snapshot_digest != source.catalog_snapshot_digest:
        raise HarborSnapshotError(
            "Harbor contract snapshot digest does not match CAP provenance"
        )
    matches: list[dict[str, Any]] = [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("capability_id") == source.harbor_capability_id
        and isinstance(record.get("contract"), dict)
    ]
    if len(matches) != 1:
        raise HarborSnapshotError(
            "Harbor contract snapshot must contain exactly one CAP contract"
        )
    contract = matches[0]["contract"]
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
