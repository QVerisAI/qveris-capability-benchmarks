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
    assert "[Try it in QVeris](https://qveris.ai/providers/okx)" in article
    assert "not a native API benchmark" in article


def test_guide_uses_a_clear_buyer_flow_without_internal_implementation_terms() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    headings = [
        "## Results",
        "## How to choose",
        "## What we tested",
        "## Reproduce or contribute",
        "## Limitations, disclosures, and corrections",
        "## FAQ",
    ]
    assert [article.index(item) for item in headings] == sorted(
        article.index(item) for item in headings
    )
    for forbidden in ("Harbor", "suite fingerprint", "run_key", "extractor"):
        assert forbidden.lower() not in article.lower()
