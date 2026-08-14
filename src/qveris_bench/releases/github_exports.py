from __future__ import annotations

import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.qveris import QverisExecutionEnvelope


def json_object(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON export: {path}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"JSON export must be an object: {path}")
    return document


def nested(document: dict[str, Any], *keys: str) -> object:
    value: object = document
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def verified_archive(
    artifact: dict[str, Any], archive_root: Path
) -> tuple[dict[str, bytes], str]:
    artifact_id = artifact.get("id")
    declared_digest = artifact.get("digest")
    if (
        not isinstance(artifact_id, int)
        or not isinstance(declared_digest, str)
        or not declared_digest.startswith("sha256:")
        or artifact.get("expired") is True
    ):
        raise ValueError("GitHub artifact identity or digest is invalid")
    archive_path = archive_root / f"{artifact_id}.zip"
    archive_digest = sha256_digest(archive_path.read_bytes())
    if archive_digest != declared_digest:
        raise ValueError("GitHub artifact archive digest mismatch")
    entries: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                path = PurePosixPath(info.filename)
                file_type = (info.external_attr >> 16) & 0o170000
                if path.is_absolute() or ".." in path.parts or file_type == 0o120000:
                    raise ValueError("GitHub artifact contains an unsafe path")
                if path.as_posix() in entries:
                    raise ValueError("GitHub artifact contains duplicate paths")
                entries[path.as_posix()] = archive.read(info)
    except zipfile.BadZipFile as exc:
        raise ValueError("GitHub artifact archive is invalid") from exc
    if not entries:
        raise ValueError("GitHub artifact archive is empty")
    return entries, archive_digest


def private_execution_document(
    entries: dict[str, bytes],
    evidence_id: str,
    envelope_digest: str,
    tool_id: str,
    parameters: dict[str, object],
) -> tuple[dict[str, Any], QverisExecutionEnvelope]:
    for name, content in entries.items():
        digest = sha256_digest(content).removeprefix("sha256:")
        path = PurePosixPath(name)
        suffix = f"-{digest}.json"
        artifact_id = name.removesuffix(suffix)
        if (
            path.name != name
            or not name.endswith(suffix)
            or artifact_id
            not in {
                f"{evidence_id}-search",
                f"{evidence_id}-search-describe",
                f"{evidence_id}-search-execute",
                f"{evidence_id}-search-execution-envelope",
            }
        ):
            raise ValueError("private raw artifact contains an unbound entry")
    envelope_name = (
        f"{evidence_id}-search-execution-envelope-"
        f"{envelope_digest.removeprefix('sha256:')}.json"
    )
    envelope_bytes = entries.get(envelope_name)
    if envelope_bytes is None or sha256_digest(envelope_bytes) != envelope_digest:
        raise ValueError("private raw artifact does not contain terminal raw digest")
    try:
        envelope = QverisExecutionEnvelope.model_validate_json(envelope_bytes)
    except ValueError as exc:
        raise ValueError("private execution envelope is invalid") from exc
    if (
        envelope.artifact_id != f"{evidence_id}-search"
        or envelope.tool_id != tool_id
        or envelope.parameters != parameters
    ):
        raise ValueError("private execution envelope request identity mismatch")
    response_name = (
        f"{evidence_id}-search-execute-"
        f"{str(envelope.response_digest).removeprefix('sha256:')}.json"
    )
    raw_bytes = entries.get(response_name)
    if raw_bytes is None or sha256_digest(raw_bytes) != envelope.response_digest:
        raise ValueError("private execution envelope response digest mismatch")
    try:
        document = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError("private raw execution is not JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("private raw execution must be an object")
    return document, envelope
