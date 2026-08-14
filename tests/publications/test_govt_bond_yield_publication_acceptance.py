from __future__ import annotations

import json
import platform
from pathlib import Path

import pytest
from PIL import Image

from qveris_bench.publications.service import (
    PublicationReproductionError,
    reproduce_publication_package,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT / "docs/guides/capability-seo/best-government-bond-yield-apis/manifest.yaml"
)
ATTESTATION = (
    ROOT / "docs/guides/publication-attestations/"
    "best-government-bond-yield-apis-2026-08-14-v1.json"
)
GUIDE = ROOT / "docs/guides/best-government-bond-yield-apis.md"
SNAPSHOT = ROOT / "selection_snapshots/govt-bond-yield-v1/selection-snapshot.json"
RELEASES = (
    ROOT / "releases/govt-bond-yield-2026-q3-v2",
    ROOT / "releases/govt-bond-yield-markets-2026-q3-v2",
)
EVIDENCE = (
    ROOT / "evidence/govt-bond-yield-2026-q3-v2",
    ROOT / "evidence/govt-bond-yield-markets-2026-q3-v2",
)


def test_government_bond_yield_publication_reproduces_from_released_facts() -> None:
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))

    report = reproduce_publication_package(
        PACKAGE,
        expected_package_digest=attestation["package_digest"],
    )

    assert report.package_id == "best-government-bond-yield-apis-2026-08-14-v1"
    assert report.release_count == 2
    assert report.status == (
        "verified"
        if platform.system() == "Linux"
        else "verified_with_noncanonical_chart_bytes"
    )
    assert report.checks == (
        "releases",
        "selection_snapshot",
        "charts",
        "article_facts",
        "links",
    )


def test_publication_renderer_is_hermetic_after_dividend_renderer_import() -> None:
    from qveris_bench.cap_packs.dividend_events import selection_charts

    assert selection_charts is not None
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))

    report = reproduce_publication_package(
        PACKAGE,
        expected_package_digest=attestation["package_digest"],
    )

    assert report.release_count == 2


def test_snapshot_and_guide_preserve_observed_boundaries() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    rows = {row["provider_id"]: row for row in snapshot["rows"]}
    fred = {
        result["market"]: result["state"]
        for result in rows["stlouisfed-fred"]["market_coverage"]["results"]
    }
    qveris_finance = {
        result["market"]: result["state"]
        for result in rows["qveris-finance"]["market_coverage"]["results"]
    }
    article = GUIDE.read_text(encoding="utf-8")

    assert fred == {
        "AU": "verified",
        "CA": "verified",
        "CN": "evidence_insufficient",
        "DE": "verified",
        "JP": "verified",
        "UK": "verified",
        "US": "verified",
    }
    assert qveris_finance == {
        "AU": "provider_negative",
        "CA": "provider_negative",
        "CN": "provider_negative",
        "DE": "provider_negative",
        "JP": "provider_negative",
        "UK": "provider_negative",
        "US": "verified",
    }
    assert "36 release-backed live calls" in article
    assert "across seven representative markets" in article
    assert "plausible benchmark tied to a different country identity" in article
    assert "identity basis `request_bound`" in article
    assert "identity basis `response_field`" in article
    assert "did not independently echo benchmark identity" in article
    assert "preserve the frozen request-series mapping" in article
    assert "market-coverage.png" in article
    assert "latency-list-price-tradeoff.png" in article

    chart = PACKAGE.parent / "charts/market-coverage.png"
    with Image.open(chart) as image:
        pixels = image.convert("RGBA")
        width, height = pixels.size
        background = pixels.getpixel((0, 0))
        assert width >= 2000 and height >= 1000
        assert all(pixels.getpixel((x, 0)) == background for x in range(width))
        assert all(pixels.getpixel((x, height - 1)) == background for x in range(width))
        assert all(pixels.getpixel((0, y)) == background for y in range(height))
        assert all(pixels.getpixel((width - 1, y)) == background for y in range(height))


def test_public_release_and_evidence_exclude_account_billed_credits() -> None:
    public_files = tuple(
        path
        for directory in (*RELEASES, *EVIDENCE)
        for path in directory.rglob("*.json")
    )

    assert len(public_files) > 36
    assert all(b'"cost_credits"' not in path.read_bytes() for path in public_files)


def test_publication_rejects_a_wrong_external_attestation() -> None:
    with pytest.raises(
        PublicationReproductionError,
        match="package digest does not match expected digest",
    ):
        reproduce_publication_package(
            PACKAGE,
            expected_package_digest="sha256:" + "0" * 64,
        )
