from __future__ import annotations

import hashlib
import importlib
import json
import platform
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qveris_bench.models.publication import PublicationPackageSpec
from qveris_bench.profiles.selection import build_selection_snapshot
from qveris_bench.publications.service import (
    PublicationReproductionError,
    resolve_repository_path,
)

_PROVIDER_NAMES = {
    "hangseng": "Hang Seng",
    "ifind": "iFinD",
    "alpha-vantage": "Alpha Vantage",
    "twelve-data": "Twelve Data",
    "eodhd": "EODHD",
    "massive-stocks": "Massive",
}


class DividendEventsPublicationAdapter:
    adapter_id = "dividend-events-v1"
    adapter_version = "1.0.0"
    cap_id = "MKT.DIVIDENDS"

    def reproduce(
        self,
        *,
        repository_root: Path,
        package_path: Path,
        package: PublicationPackageSpec,
        document: Mapping[str, Any],
        output_dir: Path,
    ) -> tuple[str, ...]:
        del package_path, package
        artifacts = _mapping(document, "artifacts")
        snapshot_input = _artifact(
            repository_root, artifacts, "selection_snapshot_input"
        )
        committed_snapshot = _artifact(repository_root, artifacts, "selection_snapshot")
        fresh_snapshot = build_selection_snapshot(snapshot_input, repository_root)
        if fresh_snapshot.json_bytes != committed_snapshot.read_bytes():
            raise PublicationReproductionError(
                "selection snapshot differs from a fresh release-derived build"
            )

        render_selection_tradeoff = _selection_renderer(repository_root)
        chart_dir = output_dir / "charts"
        generated = render_selection_tradeoff(committed_snapshot, chart_dir)
        committed_chart_manifest = _artifact(
            repository_root, artifacts, "selection_charts_manifest"
        )
        expected_manifest_digest = artifacts.get("selection_charts_manifest_digest")
        if expected_manifest_digest != _digest(committed_chart_manifest.read_bytes()):
            raise PublicationReproductionError(
                "selection chart manifest digest mismatch"
            )
        committed = json.loads(committed_chart_manifest.read_text(encoding="utf-8"))
        for field in ("data", "input_digests", "rendered_at"):
            if generated[field] != committed[field]:
                raise PublicationReproductionError(
                    f"chart {field} differs from the committed chart manifest"
                )
        charts = artifacts.get("charts")
        if not isinstance(charts, list) or not charts:
            raise PublicationReproductionError("publication charts must be declared")
        for chart_value in charts:
            if not isinstance(chart_value, str):
                raise PublicationReproductionError("invalid publication chart path")
            committed_chart = resolve_repository_path(repository_root, chart_value)
            expected = committed["charts"].get(committed_chart.name)
            if expected != _digest(committed_chart.read_bytes()):
                raise PublicationReproductionError(
                    f"committed chart digest mismatch: {committed_chart.name}"
                )
            generated_chart = chart_dir / committed_chart.name
            if platform.system() == "Linux" and (
                generated_chart.read_bytes() != committed_chart.read_bytes()
            ):
                raise PublicationReproductionError(
                    f"canonical chart bytes differ: {committed_chart.name}"
                )

        snapshot = json.loads(committed_snapshot.read_text(encoding="utf-8"))
        article = _artifact(repository_root, artifacts, "article")
        article_text = article.read_text(encoding="utf-8")
        _validate_article_facts(article_text, snapshot, document, repository_root)
        _validate_links(article_text, document, article, repository_root)
        return ("selection_snapshot", "charts", "article_facts", "links")


def _selection_renderer(repository_root: Path) -> Any:
    root_value = str(repository_root)
    added = root_value not in sys.path
    if added:
        sys.path.insert(0, root_value)
    try:
        module = importlib.import_module("scripts.render_cap_guide_charts")
    finally:
        if added:
            sys.path.remove(root_value)
    return module.render_selection_tradeoff


def _validate_article_facts(
    article: str,
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    repository_root: Path,
) -> None:
    rows = snapshot.get("rows")
    if not isinstance(rows, list) or not rows:
        raise PublicationReproductionError("selection snapshot has no rows")
    policy = _mapping(manifest, "publication_policy")
    order = policy.get("display_order")
    if not isinstance(order, list):
        raise PublicationReproductionError("article display order is missing")
    try:
        ordered_rows = sorted(rows, key=lambda row: order.index(row["access_path_id"]))
    except (ValueError, TypeError) as exc:
        raise PublicationReproductionError(
            "article display order does not cover every Access Path"
        ) from exc
    if [row["access_path_id"] for row in ordered_rows] != order:
        raise PublicationReproductionError(
            "article display order does not match every Access Path"
        )

    overview = _markdown_table_rows(article, "| Provider and Access Path |")
    pricing = _markdown_table_rows(article, "| Provider / Access Path |")
    market = _markdown_table_rows(article, "Representative markets passed (")
    expected_names = [_PROVIDER_NAMES[str(row["provider_id"])] for row in ordered_rows]
    for table in (overview, pricing, market):
        try:
            published_names = [
                next(name for name in expected_names if name in table_row[0])
                for table_row in table
            ]
        except StopIteration as exc:
            raise PublicationReproductionError(
                "article contains an unknown Provider row"
            ) from exc
        if published_names != expected_names:
            raise PublicationReproductionError("article Provider order drifted")

    for row in ordered_rows:
        provider = _PROVIDER_NAMES[str(row["provider_id"])]
        access = "Native MCP" if row["access_path_type"] == "native_mcp" else "QVeris"
        overview_row = _provider_row(overview, provider, access)
        metrics = row["gateway_metrics"]
        if metrics["state"] == "measured":
            amount = row["qveris_list_price"]["amount_credits"]
            unit = "credit/call" if amount == 1 else "credits/call"
            expected_runtime = (
                f"{metrics['latency_median_ms']:.0f} ms / {amount:g} {unit}"
            )
            _require(
                expected_runtime in overview_row[2], f"runtime fact drifted: {provider}"
            )
        else:
            _require(
                "Not applicable" in overview_row[2],
                f"runtime scope drifted: {provider}",
            )

        pricing_row = _provider_row(pricing, provider, access)
        official = row["official_pricing"]
        if official["state"] == "declared":
            _require(
                official["pricing_url"] in pricing_row[0],
                f"pricing URL drifted: {provider}",
            )
            _require(
                official["free_tier"] in pricing_row[1],
                f"free tier drifted: {provider}",
            )
            _require(
                official["paid_plans"] in pricing_row[2],
                f"paid plan drifted: {provider}",
            )

        market_row = _provider_row(market, provider, access)
        results = row["market_coverage"]["results"]
        expected_sets = [
            {item["market"] for item in results if item["state"] == state}
            for state in ("verified", "provider_negative", "not_applicable")
        ]
        published_sets = [_market_set(cell) for cell in market_row[1:4]]
        _require(published_sets == expected_sets, f"market facts drifted: {provider}")

    release_sections = manifest["publication_package"]["release_sections"]
    releases = [
        json.loads(
            resolve_repository_path(
                repository_root,
                str(_mapping(manifest, section)["directory"]) + "/release.json",
            ).read_text(encoding="utf-8")
        )
        for section in release_sections
    ]
    total_calls = sum(len(release["evidence"]) for release in releases)
    _require(
        f"We made {total_calls} live calls" in article, "article call total drifted"
    )
    _require(
        article.splitlines()[0]
        == f"# Best Dividend APIs for Developers in 2026: {len(rows)} Providers",
        "article title Provider count drifted",
    )


def _validate_links(
    article: str,
    manifest: Mapping[str, Any],
    article_path: Path,
    repository_root: Path,
) -> None:
    seo = _mapping(manifest, "seo")
    allowed = seo.get("github_links")
    actual = re.findall(r"\]\((https://github\.com/[^)]+)\)", article)
    _require(actual == allowed, "article GitHub links differ from the allowlist")
    for target in re.findall(r"\]\(([^)]+)\)", article):
        if target.startswith(("https://", "http://", "mailto:", "#")):
            continue
        resolved = (article_path.parent / target.split("#", 1)[0]).resolve()
        try:
            relative = resolved.relative_to(repository_root.resolve())
        except ValueError as exc:
            raise PublicationReproductionError(
                "article link must stay inside the repository"
            ) from exc
        resolve_repository_path(repository_root, str(relative))


def _markdown_table_rows(article: str, header_fragment: str) -> list[list[str]]:
    lines = article.splitlines()
    try:
        header_index = next(
            index for index, line in enumerate(lines) if header_fragment in line
        )
    except StopIteration as exc:
        raise PublicationReproductionError(
            f"article table is missing: {header_fragment}"
        ) from exc
    rows: list[list[str]] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def _provider_row(rows: list[list[str]], provider: str, access: str) -> list[str]:
    matches = [row for row in rows if provider in row[0] and access in row[0]]
    if len(matches) != 1:
        raise PublicationReproductionError(
            f"article must contain one row for {provider} / {access}"
        )
    return matches[0]


def _market_set(cell: str) -> set[str]:
    if cell == "—":
        return set()
    return set(re.split("[：:]", cell, maxsplit=1)[0].split(", "))


def _mapping(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = document.get(key)
    if not isinstance(value, Mapping):
        raise PublicationReproductionError(
            f"publication field must be a mapping: {key}"
        )
    return value


def _artifact(
    repository_root: Path,
    artifacts: Mapping[str, Any],
    key: str,
) -> Path:
    value = artifacts.get(key)
    if not isinstance(value, str):
        raise PublicationReproductionError(f"missing publication artifact: {key}")
    return resolve_repository_path(repository_root, value)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublicationReproductionError(message)


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
