"""Acceptance tests for scripts/export_harbor_catalog.py."""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts.export_harbor_catalog import build_contract_url, export_catalog, main


def _catalog(items: list[dict]) -> dict:
    return {"items": items, "total": len(items)}


def _fake_fetch(responses: dict[str, dict]) -> object:
    def fetch(url: str, key: str) -> dict:
        if url not in responses:
            raise RuntimeError(f"unexpected url {url}")
        return responses[url]

    return fetch


def test_main_missing_key_fails_fast(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("QVERIS_HARBOR_EXPLORE_KEY", raising=False)
    assert main(["--output", "/tmp/benchmark-export-test-missing"]) == 2
    assert "QVERIS_HARBOR_EXPLORE_KEY is required" in capsys.readouterr().err


def test_export_writes_expected_files(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QVERIS_HARBOR_EXPLORE_KEY", "hbr_test")
    catalog = _catalog(
        [{"capability_id": "MKT.BARS.EOD"}, {"capability_id": "MKT.L1.RT"}]
    )
    contract_eod = {
        "capability_id": "MKT.BARS.EOD",
        "standard_query": {"required": [{"name": "symbol"}]},
    }
    fetch = _fake_fetch(
        {
            "https://harbor.qveris.cloud/api/v2/explore/catalog": catalog,
            "https://harbor.qveris.cloud/api/v2/explore/capabilities/"
            "MKT.BARS.EOD/contract": contract_eod,
            "https://harbor.qveris.cloud/api/v2/explore/capabilities/"
            "MKT.L1.RT/contract": {"capability_id": "MKT.L1.RT"},
        }
    )
    result = export_catalog(
        "https://harbor.qveris.cloud", "hbr_test", tmp_path, fetch=fetch
    )

    assert result["counts"] == {"catalog": 2, "contracts": 2, "errors": 0}
    assert (tmp_path / "catalog.json").exists()
    assert (tmp_path / "contracts.json").exists()
    assert (tmp_path / "meta.json").exists()
    stored = json.loads((tmp_path / "contracts.json").read_text(encoding="utf-8"))
    assert stored[0]["contract"]["standard_query"]["required"][0]["name"] == "symbol"
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["origin"] == "https://harbor.qveris.cloud"
    assert meta["exporter_version"] == "1.0.0"
    assert (
        meta["catalog_snapshot_digest"]
        == hashlib.sha256((tmp_path / "contracts.json").read_bytes()).hexdigest()
    ), "AC1 export must publish the exact private snapshot digest"
    assert meta["contracts"][0] == {
        "capability_id": "MKT.BARS.EOD",
        "contract_version": None,
        "contract_digest": hashlib.sha256(
            json.dumps(
                contract_eod,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    }, "AC1 export must expose the per-contract provenance needed by a formal CAP"
    assert result["digest"] == meta["catalog_snapshot_digest"]


def test_export_contract_failure_fails_closed(tmp_path) -> None:
    catalog = _catalog(
        [{"capability_id": "MKT.BARS.EOD"}, {"capability_id": "MKT.BARS.INTRADAY"}]
    )

    def fetch(url: str, key: str) -> dict:
        if url.endswith("/contract"):
            raise RuntimeError("GET ... -> HTTP 404")
        return catalog

    with pytest.raises(RuntimeError, match="incomplete"):
        export_catalog("https://harbor.qveris.cloud", "hbr_test", tmp_path, fetch=fetch)


def test_contract_url_quotes_capability_id() -> None:
    assert (
        build_contract_url("https://harbor.qveris.cloud", "MKT.BARS.EOD")
        == "https://harbor.qveris.cloud/api/v2/explore/capabilities/MKT.BARS.EOD/contract"
    )
