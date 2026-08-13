from __future__ import annotations

import json
import platform
import shutil
import socket
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from qveris_bench.cap_packs.crypto_spot_quote.publication import (
    _validate_crypto_public_facts,
    build_crypto_selection_snapshot,
)
from qveris_bench.cli import app
from qveris_bench.models.selection import SelectionSnapshot
from qveris_bench.publications.service import (
    PublicationReproductionError,
    reproduce_publication_package,
)

ROOT = Path(__file__).resolve().parents[2]
PUBLICATION = ROOT / "docs/guides/capability-seo/best-crypto-spot-quote-apis"
PACKAGE = PUBLICATION / "manifest.yaml"
RUNNER = CliRunner()


def _copy_repository(tmp_path: Path) -> Path:
    copied = tmp_path / "repository"
    copied.mkdir(parents=True)
    shutil.copy2(ROOT / "pyproject.toml", copied / "pyproject.toml")
    for relative in (
        "cap_packs/crypto-spot-quote",
        "docs/guides/capability-seo/best-crypto-spot-quote-apis",
        "evidence/crypto-spot-quote-2026-q3-v1",
        "harbor_catalog",
        "providers",
        "releases/crypto-spot-quote-2026-q3-v1",
        "src/qveris_bench/cap_packs/crypto_spot_quote/publication.py",
        "src/qveris_bench/cap_packs/crypto_spot_quote/publication_charts.py",
        "src/qveris_bench/profiles/selection.py",
        "src/qveris_bench/models/selection.py",
    ):
        source = ROOT / relative
        target = copied / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    article = copied / "docs/guides/best-crypto-spot-quote-apis.md"
    article.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/guides/best-crypto-spot-quote-apis.md", article)
    return copied


def test_ac1_snapshot_is_deterministic_and_release_derived() -> None:
    built = build_crypto_selection_snapshot(PUBLICATION / "selection-input.yaml", ROOT)
    committed = (PUBLICATION / "selection-snapshot.json").read_bytes()

    assert built == committed
    snapshot = json.loads(built)
    SelectionSnapshot.model_validate(snapshot)
    assert snapshot["cap_id"] == "crypto-spot-quote"
    assert snapshot["cap_release_digest"].endswith("b100f9af966987d917b200cd8638a111f")
    assert (
        sum(row["run_observations"]["planned_observations"] for row in snapshot["rows"])
        == 12
    )
    assert [
        (row["provider_id"], row["access_path_id"]) for row in snapshot["rows"]
    ] == [
        ("binance", "binance-crypto-spot-qveris"),
        ("okx", "okx-crypto-spot-qveris"),
    ]
    for row in snapshot["rows"]:
        cases = {item["case_id"]: item["outcome"] for item in row["case_observations"]}
        assert cases["crypto-btcusdt-spot-quote"]["passed"] == 3
        assert cases["crypto-invalid-spot-symbol"]["passed"] == 3
        assert len(row["run_observations"]["evidence_refs"]) == 6
        assert row["qveris_list_price"]["amount_credits"] == 1
        assert row["gateway_metrics"]["latency_sample_size"] == 3


def test_ac2_package_reproduces_offline_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QVERIS_API_KEY", raising=False)

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("publication reproduction attempted network access")

    monkeypatch.setattr(httpx.Client, "request", reject_network)
    monkeypatch.setattr(httpx.AsyncClient, "request", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    result = RUNNER.invoke(app, ["publication", "reproduce", "--package", str(PACKAGE)])

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["package_id"] == "best-crypto-spot-quote-apis-2026-08-13"
    assert report["status"] == (
        "verified"
        if platform.system() == "Linux"
        else "verified_with_noncanonical_chart_bytes"
    )
    assert report["release_count"] == 1
    assert report["checks"] == [
        "releases",
        "selection_snapshot",
        "charts",
        "article_facts",
        "links",
    ]


@pytest.mark.parametrize(
    ("relative", "old", "new", "message"),
    [
        (
            "docs/guides/best-crypto-spot-quote-apis.md",
            b"This edition ran 12 live calls",
            b"This edition ran 999 live calls",
            "article facts drifted",
        ),
        (
            "docs/guides/best-crypto-spot-quote-apis.md",
            b"OKX was the lower-latency path",
            b"Binance was the lower-latency path",
            "selection advice drifted",
        ),
        (
            "docs/guides/best-crypto-spot-quote-apis.md",
            b"https://qveris.ai/providers/okx_api_v5",
            b"https://qveris.ai/providers/okx",
            "QVeris CTA drifted",
        ),
        (
            "docs/guides/best-crypto-spot-quote-apis.md",
            b"Binance / QVeris Access Path",
            b"Binance / Native API",
            "Provider and Access Path identity drifted",
        ),
        (
            "docs/guides/capability-seo/best-crypto-spot-quote-apis/selection-snapshot.json",
            b'"latency_median_ms": 313.08',
            b'"latency_median_ms": 1.0',
            "selection snapshot differs",
        ),
        (
            "docs/guides/capability-seo/best-crypto-spot-quote-apis/qveris-list-pricing.json",
            b'"amount_credits": 1',
            b'"amount_credits": 999',
            "QVeris Inspect response provenance mismatch",
        ),
        (
            "docs/guides/capability-seo/best-crypto-spot-quote-apis/charts/crypto-asset-scope.png",
            b"PNG",
            b"BAD",
            "committed chart digest mismatch",
        ),
    ],
)
def test_ac3_material_drift_fails_closed(
    tmp_path: Path,
    relative: str,
    old: bytes,
    new: bytes,
    message: str,
) -> None:
    repository = _copy_repository(tmp_path)
    target = repository / relative
    content = target.read_bytes()
    assert old in content
    target.write_bytes(content.replace(old, new, 1))

    with pytest.raises(PublicationReproductionError, match=message):
        reproduce_publication_package(
            repository
            / "docs/guides/capability-seo/best-crypto-spot-quote-apis/manifest.yaml"
        )


def test_ac4_release_evidence_and_access_path_scope_fail_closed(tmp_path: Path) -> None:
    repository = _copy_repository(tmp_path)
    evidence_manifest = (
        repository
        / "releases/crypto-spot-quote-2026-q3-v1/public-evidence-manifest.json"
    )
    evidence_manifest.unlink()
    package = (
        repository
        / "docs/guides/capability-seo/best-crypto-spot-quote-apis/manifest.yaml"
    )
    with pytest.raises(PublicationReproductionError, match="manifest is required"):
        reproduce_publication_package(package)

    repository = _copy_repository(tmp_path / "identity")
    release = repository / "releases/crypto-spot-quote-2026-q3-v1/release.json"
    release.write_bytes(
        release.read_bytes().replace(
            b'"access_path_id": "okx-crypto-spot-qveris"',
            b'"access_path_id": "binance-crypto-spot-qveris"',
            1,
        )
    )
    package = (
        repository
        / "docs/guides/capability-seo/best-crypto-spot-quote-apis/manifest.yaml"
    )
    with pytest.raises(
        PublicationReproductionError, match="release reproduction failed"
    ):
        reproduce_publication_package(package)


def test_ac5_extra_contradictory_claim_is_rejected(tmp_path: Path) -> None:
    repository = _copy_repository(tmp_path)
    article = repository / "docs/guides/best-crypto-spot-quote-apis.md"
    article.write_text(
        article.read_text(encoding="utf-8").replace(
            "\n\n## Results",
            "\n\nThis edition ran 999 live calls and Binance was the "
            "lower-latency path."
            "\n\n## Results",
        ),
        encoding="utf-8",
    )

    with pytest.raises(PublicationReproductionError, match="unexpected material claim"):
        reproduce_publication_package(
            repository
            / "docs/guides/capability-seo/best-crypto-spot-quote-apis/manifest.yaml"
        )


@pytest.mark.parametrize(
    "claim",
    [
        "Binance had a 99 ms median gateway latency in this edition.",
        "The benchmark made 999 provider requests.",
        "Binance is faster.",
        "This is a native API benchmark.",
        "Read http://example.com for details.",
    ],
)
def test_ac5_unbound_material_claims_are_rejected(tmp_path: Path, claim: str) -> None:
    repository = _copy_repository(tmp_path)
    article = repository / "docs/guides/best-crypto-spot-quote-apis.md"
    article.write_text(
        article.read_text(encoding="utf-8").replace(
            "\n\n## Results", f"\n\n{claim}\n\n## Results"
        ),
        encoding="utf-8",
    )
    with pytest.raises(PublicationReproductionError):
        reproduce_publication_package(
            repository
            / "docs/guides/capability-seo/best-crypto-spot-quote-apis/manifest.yaml"
        )


def test_ac6_public_pricing_snapshot_is_sanitized_and_scoped() -> None:
    pricing = json.loads(
        (PUBLICATION / "qveris-list-pricing.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(pricing).lower()

    assert pricing["source"] == "qveris_inspect"
    assert {item["tool_id"] for item in pricing["prices"]} == {
        "binance.ticker.24hr.retrieve.v1",
        "okx_api_v5.market.ticker.retrieve.v5.e878da46",
    }
    assert "remaining_credits" not in serialized
    assert "search_id" not in serialized
    assert "api_key" not in serialized


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b'"exchange": "BINANCE"', b'"exchange": "OKX"'),
        (b'"currency": "USDT"', b'"currency": "USD"'),
        (b'"price": 63895.28', b'"price": NaN'),
    ],
)
def test_ac7_terminal_identity_and_finite_values_are_required(
    tmp_path: Path, old: bytes, new: bytes
) -> None:
    repository = _copy_repository(tmp_path)
    terminal = next(
        (repository / "evidence/crypto-spot-quote-2026-q3-v1").glob(
            "*binance*btc*round*"
        ),
        None,
    )
    if terminal is None:
        terminal = next(
            path
            for path in (repository / "evidence/crypto-spot-quote-2026-q3-v1").glob(
                "*.json"
            )
            if b'"exchange": "BINANCE"' in path.read_bytes()
        )
    content = terminal.read_bytes()
    assert old in content
    terminal.write_bytes(content.replace(old, new, 1))
    with pytest.raises(PublicationReproductionError, match="terminal facts drifted"):
        _validate_crypto_public_facts(
            repository
            / (
                "docs/guides/capability-seo/best-crypto-spot-quote-apis/"
                "selection-input.yaml"
            ),
            repository,
        )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "benchmark_id: crypto-spot-quote-2026-q3-v1",
            "benchmark_id: crypto-spot-quote-2026-q3-v2",
        ),
        (
            "article_slug: best-crypto-spot-quote-apis",
            "article_slug: alternate-crypto-spot-quote-apis",
        ),
        ("direct_test_required: true", "direct_test_required: false"),
        ("no_overall_winner: true", "no_overall_winner: false"),
    ],
)
def test_ac8_manifest_identity_and_policy_are_cross_bound(
    tmp_path: Path, old: str, new: str
) -> None:
    repository = _copy_repository(tmp_path)
    package = (
        repository
        / "docs/guides/capability-seo/best-crypto-spot-quote-apis/manifest.yaml"
    )
    document = package.read_text(encoding="utf-8")
    assert old in document
    package.write_text(document.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(
        PublicationReproductionError, match="publication identity or policy drifted"
    ):
        reproduce_publication_package(package)
