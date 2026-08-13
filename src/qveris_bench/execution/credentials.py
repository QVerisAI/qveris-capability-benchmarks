from __future__ import annotations

import json
import os
from pathlib import Path


class QverisCredentialError(ValueError):
    pass


def load_qveris_api_key() -> str:
    key = os.environ.get("QVERIS_API_KEY")
    if isinstance(key, str) and key.strip():
        return key
    config_path = Path.home() / ".config" / "qveris" / "config.json"
    try:
        document = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        document = None
    key = document.get("api_key") if isinstance(document, dict) else None
    if not isinstance(key, str) or not key.strip():
        raise QverisCredentialError(
            "QVERIS_API_KEY is required, or authenticate with the QVeris CLI locally"
        )
    return key
