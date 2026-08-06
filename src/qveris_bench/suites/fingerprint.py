from __future__ import annotations

import hashlib
import json
from typing import Any


class ResumeFingerprintError(ValueError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def suite_fingerprint(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest()


def assert_resume_fingerprint(expected: str, actual: str) -> None:
    if expected != actual:
        raise ResumeFingerprintError(
            f"suite fingerprint mismatch: expected {expected}, received {actual}"
        )
