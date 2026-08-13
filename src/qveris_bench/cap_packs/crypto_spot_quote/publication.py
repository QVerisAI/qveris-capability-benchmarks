from __future__ import annotations

import hashlib
import json
import math
import platform
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageChops

from qveris_bench.models.publication import PublicationPackageSpec
from qveris_bench.profiles.selection import build_selection_snapshot
from qveris_bench.publications.service import (
    PublicationReproductionError,
    resolve_repository_path,
)
from qveris_bench.suites.fingerprint import canonical_json_bytes
from qveris_bench.yaml_io import load_yaml_mapping

_POSITIVE_CASE = "crypto-btcusdt-spot-quote"
_NEGATIVE_CASE = "crypto-invalid-spot-symbol"
_PROVIDER_NAMES = {"binance": "Binance", "okx": "OKX"}


class CryptoSpotQuotePublicationAdapter:
    adapter_id = "crypto-spot-quote-v1"
    adapter_version = "1.0.0"
    cap_id = "crypto-spot-quote"

    def reproduce(
        self,
        *,
        repository_root: Path,
        package_path: Path,
        package: PublicationPackageSpec,
        document: Mapping[str, Any],
        output_dir: Path,
    ) -> tuple[str, ...]:
        del package_path
        if package.release_sections != ("release",):
            raise PublicationReproductionError(
                "Crypto Spot Quote publication requires exactly one Release"
            )
        artifacts = _mapping(document, "artifacts")
        selection_input = _artifact(
            repository_root, artifacts, "selection_snapshot_input"
        )
        committed_snapshot = _artifact(repository_root, artifacts, "selection_snapshot")
        fresh_snapshot = build_crypto_selection_snapshot(
            selection_input, repository_root
        )
        if fresh_snapshot != committed_snapshot.read_bytes():
            raise PublicationReproductionError(
                "selection snapshot differs from a fresh release-derived build"
            )
        snapshot = _json_mapping(committed_snapshot, "selection snapshot")
        if snapshot.get("cap_id") != package.cap_id:
            raise PublicationReproductionError(
                "publication package CAP does not match the Selection Snapshot"
            )
        _validate_manifest(document, artifacts, selection_input, committed_snapshot)

        generated = _render_charts(committed_snapshot, output_dir)
        _validate_charts(generated, artifacts, repository_root, output_dir)

        article_facts_path = _artifact(repository_root, artifacts, "article_facts")
        article_facts = _build_article_facts(snapshot, document, repository_root)
        expected_facts = canonical_json_bytes(article_facts)
        if article_facts_path.read_bytes() != expected_facts:
            raise PublicationReproductionError(
                "article facts differ from fresh release-derived facts"
            )
        if artifacts.get("article_facts_digest") != _digest(expected_facts):
            raise PublicationReproductionError("article facts digest mismatch")

        article_path = _artifact(repository_root, artifacts, "article")
        article = article_path.read_text(encoding="utf-8")
        profile = load_yaml_mapping(
            _artifact(repository_root, artifacts, "publication_profile")
        )
        _validate_article(article, article_facts, snapshot, document, profile)
        _validate_links(article, document)
        return ("selection_snapshot", "charts", "article_facts", "links")


def build_crypto_selection_snapshot(input_path: Path, root: Path) -> bytes:
    built = build_selection_snapshot(input_path, root)
    _validate_crypto_public_facts(input_path, root)
    return built.json_bytes


def _validate_crypto_public_facts(input_path: Path, root: Path) -> None:
    config = load_yaml_mapping(input_path)
    release_spec = _mapping(config, "cap_release")
    release_path = resolve_repository_path(root, _string(release_spec, "release"))
    release = _json_mapping(release_path, "Crypto Release")
    release_dir = release_path.parent
    manifest = _json_mapping(
        release_dir / "public-evidence-manifest.json", "public evidence manifest"
    )
    public_by_run = _unique_by(
        _list_of_mappings(manifest, "evidence"), "run_key", "public evidence"
    )
    expected_exchange = {"binance": "BINANCE", "okx": "OKX"}
    for cell in _list_of_mappings(release, "cells"):
        if cell.get("case_id") != _POSITIVE_CASE:
            continue
        entry = public_by_run.get(_string(cell, "run_key"))
        if entry is None:
            raise PublicationReproductionError("Crypto public evidence is incomplete")
        terminal = _terminal(root, entry, cell)
        facts = _mapping(terminal, "facts")
        provider_id = _string(cell, "provider_id")
        values = [facts.get(field) for field in ("price", "open", "high", "low")]
        if (
            facts.get("symbol") != "BTCUSDT"
            or facts.get("currency") != "USDT"
            or facts.get("exchange") != expected_exchange.get(provider_id)
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0
                for value in values
            )
        ):
            raise PublicationReproductionError("Crypto terminal facts drifted")


def _terminal(
    root: Path, entry: Mapping[str, Any], cell: Mapping[str, Any]
) -> Mapping[str, Any]:
    terminal = _json_mapping(
        resolve_repository_path(root, _string(entry, "path")), "public terminal"
    )
    if (
        terminal.get("run_key") != cell.get("run_key")
        or terminal.get("case_id") != cell.get("case_id")
        or terminal.get("round") != cell.get("round")
        or terminal.get("state") != cell.get("state")
    ):
        raise PublicationReproductionError(
            "public terminal Provider, Access Path, or run identity drifted"
        )
    return terminal


def _build_article_facts(
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    root: Path,
) -> dict[str, object]:
    del root
    rows = _list_of_mappings(snapshot, "rows")
    fastest = min(
        rows,
        key=lambda row: float(_mapping(row, "gateway_metrics")["latency_median_ms"]),
    )
    fact_rows: list[dict[str, object]] = []
    for row in rows:
        cases = {
            _string(case, "case_id"): _mapping(case, "outcome")
            for case in _list_of_mappings(row, "case_observations")
        }
        run = _mapping(row, "run_observations")
        fact_rows.append(
            {
                "access_path_id": row["access_path_id"],
                "access_path_type": row["access_path_type"],
                "evidence_ref_count": len(run.get("evidence_refs", [])),
                "invalid_input": cases[_NEGATIVE_CASE],
                "latency_median_ms": _mapping(row, "gateway_metrics")[
                    "latency_median_ms"
                ],
                "official_pricing": row["official_pricing"],
                "positive": cases[_POSITIVE_CASE],
                "provider_id": row["provider_id"],
                "provider_name": row["provider_name"],
                "qveris_list_price": row["qveris_list_price"],
                "qveris_provider_page": _mapping(
                    _mapping(manifest, "seo"), "provider_pages"
                )[str(row["provider_name"])],
            }
        )
    total_calls = sum(
        int(_mapping(row, "run_observations")["planned_observations"]) for row in rows
    )
    evidence_records = sum(
        len(_mapping(row, "run_observations").get("evidence_refs", [])) for row in rows
    )
    return {
        "access_path_count": len(rows),
        "edition": snapshot["edition"],
        "package_id": _mapping(manifest, "publication_package")["package_id"],
        "provider_count": len({row["provider_id"] for row in rows}),
        "recommendations": {
            "fastest_observed_path": {
                "access_path_id": fastest["access_path_id"],
                "provider_name": fastest["provider_name"],
            },
            "same_qveris_list_price": len(
                {_mapping(row, "qveris_list_price")["amount_credits"] for row in rows}
            )
            == 1,
        },
        "release": {
            "applicable_cells": total_calls,
            "negative_control_cells": sum(
                int(_mapping(row, "invalid_input")["total"]) for row in fact_rows
            ),
            "observation_date": snapshot["edition"],
            "planned_cells": total_calls,
            "positive_case_cells": sum(
                int(_mapping(row, "positive")["total"]) for row in fact_rows
            ),
            "public_evidence_records": evidence_records,
            "release_digest": snapshot["cap_release_digest"],
            "release_id": snapshot["cap_release_id"],
            "rounds_per_cell": max(
                int(_mapping(row, "positive")["total"]) for row in fact_rows
            ),
        },
        "rows": fact_rows,
        "schema_version": 1,
        "total_live_calls": total_calls,
    }


def _validate_manifest(
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    selection_input: Path,
    snapshot_path: Path,
) -> None:
    snapshot = _json_mapping(snapshot_path, "selection snapshot")
    selection = _mapping(manifest, "selection_snapshot")
    if (
        str(manifest.get("edition")) != snapshot.get("edition")
        or selection.get("id") != snapshot.get("snapshot_id")
        or selection.get("input_digest") != _file_digest(selection_input)
        or selection.get("digest") != _file_digest(snapshot_path)
    ):
        raise PublicationReproductionError("selection manifest metadata drifted")
    release = _mapping(manifest, "release")
    if (
        release.get("digest") != snapshot.get("cap_release_digest")
        or release.get("suite_fingerprint") != snapshot.get("suite_fingerprint")
        or release.get("planned_cells") != 12
        or release.get("applicable_cells") != 12
        or release.get("public_evidence_records") != 12
        or release.get("rounds_per_cell") != 3
    ):
        raise PublicationReproductionError("publication Release metadata drifted")
    package = _mapping(manifest, "publication_package")
    policy = _mapping(manifest, "publication_policy")
    article_path = str(artifacts.get("article", ""))
    if (
        manifest.get("benchmark_id") != "crypto-spot-quote-2026-q3-v1"
        or manifest.get("article_slug") != "best-crypto-spot-quote-apis"
        or not article_path.endswith("/best-crypto-spot-quote-apis.md")
        or package.get("package_id") != "best-crypto-spot-quote-apis-2026-08-13"
        or policy.get("display_order")
        != ["binance-crypto-spot-qveris", "okx-crypto-spot-qveris"]
        or policy.get("direct_test_required") is not True
        or policy.get("no_overall_winner") is not True
        or policy.get("scope_claim") != "BTC/USDT spot sample only"
    ):
        raise PublicationReproductionError("publication identity or policy drifted")
    if not isinstance(artifacts.get("charts"), list) or len(artifacts["charts"]) != 2:
        raise PublicationReproductionError("publication chart set drifted")
    seo = _mapping(manifest, "seo")
    title = str(seo.get("title", ""))
    description = str(seo.get("meta_description", ""))
    if not 40 <= len(title) <= 60 or not 150 <= len(description) <= 160:
        raise PublicationReproductionError("publication SEO metadata drifted")


def _render_charts(snapshot: Path, output_dir: Path) -> dict[str, object]:
    from qveris_bench.cap_packs.crypto_spot_quote.publication_charts import (
        render_crypto_publication_charts,
    )

    return render_crypto_publication_charts(snapshot, output_dir / "charts")


def _validate_charts(
    generated: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    root: Path,
    output_dir: Path,
) -> None:
    manifest_path = _artifact(root, artifacts, "selection_charts_manifest")
    if artifacts.get("selection_charts_manifest_digest") != _file_digest(manifest_path):
        raise PublicationReproductionError("selection chart manifest digest mismatch")
    committed = _json_mapping(manifest_path, "selection chart manifest")
    for field in ("data", "input_digests", "rendered_at", "renderer"):
        if committed.get(field) != generated.get(field):
            raise PublicationReproductionError(
                f"chart {field} differs from the committed chart manifest"
            )
    chart_values = artifacts.get("charts")
    if not isinstance(chart_values, list) or not all(
        isinstance(value, str) for value in chart_values
    ):
        raise PublicationReproductionError("publication charts must be declared")
    names = {Path(value).name for value in chart_values}
    committed_charts = _mapping(committed, "charts")
    generated_charts = _mapping(generated, "charts")
    if names != set(committed_charts) or names != set(generated_charts):
        raise PublicationReproductionError(
            "declared, committed, and generated chart sets must match"
        )
    for value in chart_values:
        path = resolve_repository_path(root, value)
        if committed_charts.get(path.name) != _file_digest(path):
            raise PublicationReproductionError(
                f"committed chart digest mismatch: {path.name}"
            )
        generated_path = output_dir / "charts" / path.name
        if not _same_pixels(generated_path, path):
            raise PublicationReproductionError(
                f"canonical chart pixels differ: {path.name}"
            )
        if (
            platform.system() == "Linux"
            and generated_path.read_bytes() != path.read_bytes()
        ):
            raise PublicationReproductionError(
                f"canonical chart bytes differ: {path.name}"
            )


def _validate_article(
    article: str,
    facts: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> None:
    seo = _mapping(manifest, "seo")
    title = _string(seo, "title")
    description = _string(seo, "meta_description")
    if (
        f'title: "{title}"' not in article
        or f'description: "{description}"' not in article
        or f"# {title}" not in article
    ):
        raise PublicationReproductionError("article SEO facts drifted")
    flow = profile.get("required_flow")
    if not isinstance(flow, list):
        raise PublicationReproductionError("publication profile is invalid")
    headings = [f"## {heading}" for heading in flow]
    if any(heading not in article for heading in headings) or [
        article.index(heading) for heading in headings
    ] != sorted(article.index(heading) for heading in headings):
        raise PublicationReproductionError("article buyer flow drifted")

    rows = _list_of_mappings(facts, "rows")
    result_rows = _markdown_table_rows(
        article, "| Tested path | BTC/USDT required fields |"
    )
    expected_results = [
        [
            f"{row['provider_name']} / QVeris Access Path",
            f"Sample passed, {row['positive']['passed']}/{row['positive']['total']}",
            "Rejected, "
            f"{row['invalid_input']['passed']}/{row['invalid_input']['total']}",
            f"{round(float(row['latency_median_ms']))} ms",
            "1 credit/call",
            _expected_links(row, manifest),
        ]
        for row in rows
    ]
    if result_rows != expected_results:
        if any("Native API" in cell for row in result_rows for cell in row):
            raise PublicationReproductionError(
                "Provider and Access Path identity drifted"
            )
        expected_pages = {str(row["qveris_provider_page"]) for row in rows}
        observed_pages = {
            value
            for row in result_rows
            for cell in row
            for value in re.findall(r"https://qveris\.ai/providers/[^)]+", cell)
        }
        if observed_pages != expected_pages:
            raise PublicationReproductionError("QVeris CTA drifted")
        raise PublicationReproductionError("article result table drifted")

    pricing_rows = _markdown_table_rows(
        article, "| Provider × Access Path | Official pricing fact |"
    )
    official_source_labels = {
        "Binance": "Binance Spot API market data",
        "OKX": "OKX market ticker API",
    }
    expected_pricing = []
    for row in rows:
        pricing = _mapping(row, "official_pricing")
        provider_name = str(row["provider_name"])
        expected_pricing.append(
            [
                f"{provider_name} / QVeris Access Path",
                f"{pricing['free_tier']} {pricing['paid_plans']}",
                str(pricing["verified_at"]),
                f"[{official_source_labels[provider_name]}]({pricing['pricing_url']})",
            ]
        )
    if pricing_rows != expected_pricing:
        raise PublicationReproductionError("official pricing facts drifted")

    agent_rows = _markdown_table_rows(
        article, "| Provider × Access Path | Positive case |"
    )
    expected_agent = [
        [
            "Binance / QVeris Access Path",
            "Sample passed, 3/3",
            "Provider rejected, 3/3",
            "`price`, `open`, `high`, `low`, 3/3",
            "Parameter clarity, pagination, and constrained Agent Trial",
        ],
        [
            "OKX / QVeris Access Path",
            "Sample passed, 3/3",
            "Provider rejected, 3/3",
            "`price`, `open`, `high`, `low`, 3/3",
            "Parameter clarity, pagination, and constrained Agent Trial",
        ],
    ]
    if agent_rows != expected_agent:
        raise PublicationReproductionError("Agent interface facts drifted")

    release = _mapping(facts, "release")
    expected_fastest = _mapping(
        _mapping(facts, "recommendations"), "fastest_observed_path"
    )
    lower_latency_claims = re.findall(
        r"(Binance|OKX) was the lower-latency path", article
    )
    wrong_latency_claims = [
        name
        for name in lower_latency_claims
        if name != expected_fastest.get("provider_name")
    ]
    if wrong_latency_claims:
        if lower_latency_claims.count(str(expected_fastest["provider_name"])) == 1:
            raise PublicationReproductionError("unexpected material claim")
        raise PublicationReproductionError("selection advice drifted")
    required_claims = (
        f"This edition ran {facts['total_live_calls']} live calls "
        f"on {facts['edition']}",
        "OKX was the lower-latency path in this small test",
        "Both paths had the same public QVeris Inspect price on 2026-08-13: "
        "1 credit/call.",
        str(release["release_digest"]),
    )
    if any(article.count(claim) != 1 for claim in required_claims):
        raise PublicationReproductionError("article facts drifted")
    live_call_values = [
        int(value) for value in re.findall(r"(\d+) live calls", article)
    ]
    if live_call_values != [12, 12]:
        if any(value != 12 for value in live_call_values):
            raise PublicationReproductionError("unexpected material claim")
        raise PublicationReproductionError("article facts drifted")
    if any(
        value != release["release_digest"]
        for value in re.findall(r"sha256:[a-f0-9]{64}", article)
    ):
        raise PublicationReproductionError("unexpected material claim")
    for value in re.findall(r"(\d+(?:\.\d+)?) credits?/call", article):
        if float(value) != 1:
            raise PublicationReproductionError("unexpected material claim")
    snapshot_calls = sum(
        int(_mapping(row, "run_observations")["planned_observations"])
        for row in _list_of_mappings(snapshot, "rows")
    )
    if snapshot_calls != facts.get("total_live_calls"):
        raise PublicationReproductionError("article facts drifted")
    stripped = re.sub(r"```.*?```", "", article, flags=re.DOTALL)
    stripped = re.sub(r"https?://[^\s)>]+", "", stripped)
    material_numbers = Counter(
        re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:/\d+)?", stripped)
    )
    expected_numbers = Counter(
        {
            "3/3": 13,
            "2026": 7,
            "08": 4,
            "13": 4,
            "1": 3,
            "12": 2,
            "24": 2,
            "313": 1,
            "286": 1,
            "5": 1,
        }
    )
    if material_numbers != expected_numbers:
        raise PublicationReproductionError("unexpected material claim")
    if re.search(r"Binance.{0,80}(?:faster|lower[- ]latency)", article, re.I):
        raise PublicationReproductionError("unexpected material claim")
    forbidden = profile.get("forbidden_claims")
    if not isinstance(forbidden, list):
        raise PublicationReproductionError("publication profile is invalid")
    for phrase in forbidden:
        if not isinstance(phrase, str):
            raise PublicationReproductionError("publication profile is invalid")
        for match in re.finditer(re.escape(phrase), article, re.I):
            prefix = article[max(0, match.start() - 40) : match.start()].lower()
            if "not " not in prefix and "no " not in prefix:
                raise PublicationReproductionError("forbidden article claim")


def _validate_links(article: str, manifest: Mapping[str, Any]) -> None:
    seo = _mapping(manifest, "seo")
    allowlist: set[str] = set()
    for key in (
        "supplier_sites",
        "provider_pages",
        "official_sources",
        "related_guides",
    ):
        allowlist.update(str(value) for value in _mapping(seo, key).values())
    github_links = seo.get("github_links")
    if not isinstance(github_links, list):
        raise PublicationReproductionError("publication GitHub links are invalid")
    allowlist.update(str(value) for value in github_links)
    observed = set(re.findall(r"\[[^]]+\]\((https://[^)]+)\)", article))
    if observed != allowlist:
        unknown = observed - allowlist
        if any("qveris.ai/providers/okx" in value for value in unknown):
            raise PublicationReproductionError("QVeris CTA drifted")
        raise PublicationReproductionError(
            "article external links differ from allowlist"
        )
    if re.search(r"(?:file://|/Users/|/home/|[A-Za-z]:\\)", article):
        raise PublicationReproductionError("article contains a local path")
    all_urls = set(re.findall(r"https?://[^\s)>]+", article))
    repository_urls = {
        value
        for value in allowlist
        if value.startswith("https://github.com/") and "/blob/" not in value
    }
    allowed_urls = allowlist | {f"{value}.git" for value in repository_urls}
    if (
        any(value.startswith("http://") for value in all_urls)
        or all_urls != allowed_urls
    ):
        raise PublicationReproductionError(
            "article external links differ from allowlist"
        )


def _expected_links(row: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    seo = _mapping(manifest, "seo")
    name = str(row["provider_name"])
    return (
        f"[{name}]({_mapping(seo, 'supplier_sites')[name]}) · "
        f"[Try it in QVeris]({_mapping(seo, 'provider_pages')[name]})"
    )


def _markdown_table_rows(article: str, header: str) -> list[list[str]]:
    lines = article.splitlines()
    try:
        start = next(
            index for index, line in enumerate(lines) if line.startswith(header)
        )
    except StopIteration as exc:
        raise PublicationReproductionError("required article table is missing") from exc
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def _unique_by(
    values: list[Mapping[str, Any]], key: str, label: str
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for value in values:
        identity = _string(value, key)
        if identity in result:
            raise PublicationReproductionError(f"{label} contains duplicate identities")
        result[identity] = value
    return result


def _same_pixels(left_path: Path, right_path: Path) -> bool:
    with Image.open(left_path) as left_image, Image.open(right_path) as right_image:
        left = left_image.convert("RGBA")
        right = right_image.convert("RGBA")
        return (
            left.size == right.size
            and ImageChops.difference(left, right).getbbox() is None
        )


def _json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationReproductionError(f"invalid {label}") from exc
    if not isinstance(value, dict):
        raise PublicationReproductionError(f"invalid {label}")
    return value


def _list_of_mappings(document: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise PublicationReproductionError(f"{key} must be a list of mappings")
    return cast(list[Mapping[str, Any]], value)


def _mapping(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = document.get(key)
    if not isinstance(value, Mapping):
        raise PublicationReproductionError(f"{key} must be a mapping")
    return cast(Mapping[str, Any], value)


def _string(document: Mapping[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise PublicationReproductionError(f"{key} must be a non-empty string")
    return value


def _artifact(root: Path, artifacts: Mapping[str, Any], key: str) -> Path:
    return resolve_repository_path(root, _string(artifacts, key))


def _file_digest(path: Path) -> str:
    return _digest(path.read_bytes())


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
