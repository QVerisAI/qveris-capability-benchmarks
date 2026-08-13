from __future__ import annotations

import json
from pathlib import Path

import pytest

from qveris_bench.execution.credentials import (
    QverisCredentialError,
    load_qveris_api_key,
)


def test_environment_key_has_precedence_over_cli_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "cli-key"}), encoding="utf-8")
    monkeypatch.setenv("QVERIS_API_KEY", "environment-key")

    assert load_qveris_api_key(path) == "environment-key"


def test_cli_config_is_local_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("QVERIS_API_KEY", raising=False)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "cli-key"}), encoding="utf-8")

    assert load_qveris_api_key(path) == "cli-key"


def test_missing_key_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("QVERIS_API_KEY", raising=False)

    with pytest.raises(QverisCredentialError, match="QVERIS_API_KEY"):
        load_qveris_api_key(tmp_path / "missing.json")
