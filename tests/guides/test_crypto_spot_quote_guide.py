from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTICLE = ROOT / "docs" / "guides" / "best-crypto-spot-quote-apis.md"
RELEASE = ROOT / "releases" / "crypto-spot-quote-2026-q3-v1" / "release.json"


def test_guide_binds_the_buyer_summary_to_the_release() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    for provider_id, access_path_id in (
        ("binance", "binance-crypto-spot-qveris"),
        ("okx", "okx-crypto-spot-qveris"),
    ):
        positive = sum(
            cell["state"] == "completed"
            and cell["case_id"] == "crypto-btcusdt-spot-quote"
            and cell["provider_id"] == provider_id
            and cell["access_path_id"] == access_path_id
            for cell in release["cells"]
        )
        rejected = sum(
            cell["state"] == "provider_negative"
            and cell["case_id"] == "crypto-invalid-spot-symbol"
            and cell["provider_id"] == provider_id
            and cell["access_path_id"] == access_path_id
            for cell in release["cells"]
        )
        assert (positive, rejected) == (3, 3)
    assert article.count("3/3") >= 4
    assert "12 live calls" in article


def test_guide_preserves_provider_and_access_path_identity() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    assert "Binance / QVeris Access Path" in article
    assert "OKX / QVeris Access Path" in article
    assert "[Try it in QVeris](https://qveris.ai/providers/binance)" in article
    assert "[Try it in QVeris](https://qveris.ai/providers/okx_api_v5)" in article
    assert "not a native API benchmark" in article


def test_guide_derives_latency_recommendation_from_public_evidence() -> None:
    evidence_path = ROOT / "releases" / "crypto-spot-quote-2026-q3-v1" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    latencies = {
        provider_id: sorted(
            item["latency_ms"]
            for item in evidence
            if ":crypto-btcusdt-spot-quote:" in item["run_key"]
            and f":{provider_id}:" in item["run_key"]
        )[1]
        for provider_id in ("binance", "okx")
    }
    assert latencies == {"binance": 313.08, "okx": 285.82}
    article = ARTICLE.read_text(encoding="utf-8")
    result_rows = {
        row.split("|")[1].strip(): row.split("|")
        for row in article.splitlines()
        if row.startswith("| ")
        and "/ QVeris Access Path" in row
        and "credit/call" in row
    }
    for provider, latency in latencies.items():
        display_name = "Binance" if provider == "binance" else "OKX"
        assert result_rows[f"{display_name} / QVeris Access Path"][4].strip() == (
            f"{round(latency):.0f} ms"
        )
    assert "OKX was the lower-latency path" in article
    assert "OKX had the lower observed median gateway latency" in article


def test_guide_uses_a_clear_buyer_flow_without_internal_implementation_terms() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    headings = [
        "## Results at a glance",
        "## How developers should choose",
        "## Tested asset scope",
        "## Method, reproduction, and contribution",
        "## Limitations, disclosures, and corrections",
        "## FAQ",
    ]
    assert [article.index(item) for item in headings] == sorted(
        article.index(item) for item in headings
    )
    for forbidden in ("Harbor", "suite fingerprint", "run_key", "extractor"):
        assert forbidden.lower() not in article.lower()
