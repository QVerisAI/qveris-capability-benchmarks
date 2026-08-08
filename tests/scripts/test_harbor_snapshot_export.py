from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.export_harbor_snapshot import export_snapshot


def _write_harbor_fixture(harbor_root: Path) -> None:
    data = harbor_root / "data"
    audit = data / "audit"
    audit.mkdir(parents=True)
    (data / "market-representative-tickers.yaml").write_text(
        yaml.safe_dump({"US": "AAPL", "CN": "600519.SH", "NO": "EQNR.OL"}),
        encoding="utf-8",
    )
    (audit / "seed_provider_test_symbols.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "entries": [
                    {
                        "provider_id": "fmp",
                        "market": "US",
                        "symbol": "AAPL",
                        "source": "test-fixture",
                        "verified_at": "2026-08-08T00:00:00+00:00",
                        "notes": "internal probe detail that must be dropped",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (audit / "market_anchors.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "markets": [
                    {
                        "market": "US",
                        "company_key": "apple",
                        "display_name": "Apple Inc",
                        "candidate_tickers": ["AAPL"],
                        "notes": "internal ADR note that must be dropped",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_export_snapshot_normalizes_and_hashes_deterministically(
    tmp_path: Path,
) -> None:
    _write_harbor_fixture(tmp_path)
    first = export_snapshot(
        tmp_path,
        tmp_path / "out",
        harbor_commit="a" * 40,
        exported_at="2026-08-08T00:00:00+00:00",
    )
    second = export_snapshot(
        tmp_path,
        tmp_path / "out2",
        harbor_commit="a" * 40,
        exported_at="2026-08-08T00:00:00+00:00",
    )

    assert first["sha256"] == second["sha256"]
    snapshot = json.loads(
        (tmp_path / "out" / first["snapshot_file"]).read_text(encoding="utf-8")
    )
    assert snapshot["schema_version"] == "1.0.0"
    assert snapshot["provenance"]["source"] == "quaestio-harbor"
    assert snapshot["provenance"]["license_note"].startswith("Private operator data")
    assert snapshot["markets"] == [
        {"market": "CN", "representative_ticker": "600519.SH"},
        {"market": "NO", "representative_ticker": "EQNR.OL"},
        {"market": "US", "representative_ticker": "AAPL"},
    ]
    assert snapshot["provider_symbol_samples"] == [
        {
            "provider_id": "fmp",
            "market": "US",
            "symbol": "AAPL",
            "source": "test-fixture",
            "verified_at": "2026-08-08T00:00:00+00:00",
        }
    ]
    assert snapshot["market_anchors"] == [
        {
            "market": "US",
            "company_key": "apple",
            "display_name": "Apple Inc",
            "candidate_tickers": ["AAPL"],
        }
    ]
    assert "notes" not in json.dumps(snapshot)


def test_export_snapshot_accepts_identifier_samples(tmp_path: Path) -> None:
    _write_harbor_fixture(tmp_path)
    identifiers = tmp_path / "identifier_samples.yaml"
    identifiers.write_text(
        yaml.safe_dump(
            {
                "entries": [
                    {
                        "market": "US",
                        "company_key": "apple_inc",
                        "identifiers": {
                            "ticker": "AAPL",
                            "cik": "0000320193",
                            "isin": "US0378331005",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = export_snapshot(
        tmp_path,
        tmp_path / "out",
        identifier_samples_path=identifiers,
        harbor_commit="a" * 40,
        exported_at="2026-08-08T00:00:00+00:00",
    )

    assert manifest["counts"]["identifier_samples"] == 1
    assert "identifier_samples.yaml" in json.dumps(manifest)
