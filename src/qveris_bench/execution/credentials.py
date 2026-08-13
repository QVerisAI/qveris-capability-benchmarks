from __future__ import annotations

import json
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class QverisCredentialError(ValueError):
    pass


class QverisCredentials(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    qveris_api_key: SecretStr | None = None


def load_qveris_api_key(config_path: Path | None = None) -> str:
    key = QverisCredentials().qveris_api_key
    if key is not None and key.get_secret_value().strip():
        return key.get_secret_value()
    path = config_path or Path.home() / ".config" / "qveris" / "config.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        document = None
    key = document.get("api_key") if isinstance(document, dict) else None
    if not isinstance(key, str) or not key.strip():
        raise QverisCredentialError(
            "QVERIS_API_KEY is required, or authenticate with the QVeris CLI locally"
        )
    return key
