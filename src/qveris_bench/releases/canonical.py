from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_release_bytes(release: Any) -> bytes:
    return (
        json.dumps(release, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def release_digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()
