from __future__ import annotations

import hashlib


def sha256_digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
