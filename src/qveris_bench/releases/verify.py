from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qveris_bench.releases.canonical import canonical_release_bytes, release_digest


def verify_release(path: Path, expected_digest: str) -> bool:
    payload: dict[str, Any] = json.loads(path.read_text())
    return release_digest(canonical_release_bytes(payload)) == expected_digest
