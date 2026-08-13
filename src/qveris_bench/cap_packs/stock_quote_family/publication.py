from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qveris_bench.cap_packs.stock_quote_family.publication_selection import (
    StockQuoteSelectionBuildError,
    build_stock_quote_selection_snapshot,
)
from qveris_bench.models.publication import PublicationPackageSpec
from qveris_bench.publications.service import (
    PublicationReproductionError,
    resolve_repository_path,
)
from qveris_bench.yaml_io import load_yaml_mapping


class StockQuotePublicationAdapter:
    adapter_id = "stock-quote-v1"
    adapter_version = "1.0.0"
    cap_id = "stock-quote"

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
                "Stock Quote publication requires exactly one family Release"
            )
        artifacts = _mapping(document, "artifacts")
        selection_input = _artifact(
            repository_root, artifacts, "selection_snapshot_input"
        )
        committed_snapshot = _artifact(repository_root, artifacts, "selection_snapshot")
        input_document = load_yaml_mapping(selection_input)
        _validate_input_paths(input_document, repository_root)
        release = _mapping(document, "release")
        input_release = _mapping(input_document, "release")
        _require(
            input_release.get("path") == f"{release.get('directory')}/release.json"
            and input_release.get("digest") == release.get("digest"),
            "selection input release differs from publication Release",
        )
        try:
            fresh = build_stock_quote_selection_snapshot(
                selection_input, repository_root
            )
        except StockQuoteSelectionBuildError as exc:
            raise PublicationReproductionError(str(exc)) from exc
        _require(
            fresh.json_bytes == committed_snapshot.read_bytes(),
            "selection snapshot differs from a fresh release-derived build",
        )

        chart_dir = output_dir / "charts"
        cache_dir = output_dir / "matplotlib-cache"
        cache_dir.mkdir()
        previous = {
            name: os.environ.get(name) for name in ("MPLCONFIGDIR", "XDG_CACHE_HOME")
        }
        os.environ["MPLCONFIGDIR"] = str(cache_dir)
        os.environ["XDG_CACHE_HOME"] = str(cache_dir)
        try:
            from qveris_bench.cap_packs.stock_quote_family.publication_charts import (
                render_stock_quote_outcomes,
            )

            generated = render_stock_quote_outcomes(committed_snapshot, chart_dir)
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        committed_chart_manifest = _artifact(
            repository_root, artifacts, "selection_charts_manifest"
        )
        _require(
            artifacts.get("selection_charts_manifest_digest")
            == _digest(committed_chart_manifest.read_bytes()),
            "selection chart manifest digest mismatch",
        )
        committed = json.loads(committed_chart_manifest.read_text(encoding="utf-8"))
        for field in ("data", "input_digests", "rendered_at"):
            _require(
                generated[field] == committed[field],
                f"chart {field} differs from the committed chart manifest",
            )
        generated_charts = generated.get("charts")
        if not isinstance(generated_charts, Mapping):
            raise PublicationReproductionError("generated chart set is invalid")
        declared = artifacts.get("charts")
        if not isinstance(declared, list) or not declared:
            raise PublicationReproductionError("publication charts must be declared")
        declared_names = {
            Path(value).name for value in declared if isinstance(value, str)
        }
        _require(
            len(declared_names) == len(declared)
            and declared_names == set(generated_charts),
            "declared, committed, and generated chart sets must match",
        )
        for value in declared:
            if not isinstance(value, str):
                raise PublicationReproductionError("invalid publication chart path")
            committed_chart = resolve_repository_path(repository_root, value)
            _require(
                committed["charts"][committed_chart.name]
                == _digest(committed_chart.read_bytes()),
                f"committed chart digest mismatch: {committed_chart.name}",
            )
            if platform.system() == "Linux":
                _require(
                    (chart_dir / committed_chart.name).is_file(),
                    f"canonical chart was not rendered: {committed_chart.name}",
                )

        snapshot = json.loads(committed_snapshot.read_text(encoding="utf-8"))
        _validate_manifest(document, artifacts, selection_input, committed_snapshot)
        article_path = _artifact(repository_root, artifacts, "article")
        article = article_path.read_text(encoding="utf-8")
        _validate_article(article, snapshot, document, input_document)
        _validate_links(article, document, article_path, repository_root)
        return ("selection_snapshot", "charts", "article_facts", "links")


def _validate_manifest(
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    selection_input: Path,
    snapshot_path: Path,
) -> None:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    selection = _mapping(manifest, "selection_snapshot")
    _require(
        str(manifest.get("edition")) == snapshot["edition"],
        "publication edition mismatch",
    )
    _require(
        selection.get("id") == snapshot["snapshot_id"],
        "selection snapshot identity mismatch",
    )
    _require(
        selection.get("input_digest") == _digest(selection_input.read_bytes()),
        "selection snapshot input digest mismatch",
    )
    _require(
        selection.get("digest") == _digest(snapshot_path.read_bytes()),
        "selection snapshot digest mismatch",
    )
    release = _mapping(manifest, "release")
    rows = snapshot["rows"]
    all_results = [result for row in rows for result in row["case_results"]]
    _require(
        release.get("digest") == snapshot["release_digest"], "release digest mismatch"
    )
    _require(
        release.get("suite_fingerprint") == snapshot["suite_fingerprint"],
        "release suite fingerprint mismatch",
    )
    _require(release.get("planned_cells") == 30, "release planned cell count mismatch")
    _require(
        release.get("applicable_cells") == 30, "release applicable cell count mismatch"
    )
    _require(
        release.get("public_evidence_records")
        == sum(result["total_rounds"] for result in all_results),
        "release public evidence count mismatch",
    )
    rounds = {result["total_rounds"] for result in all_results}
    _require(
        len(rounds) == 1 and release.get("rounds_per_cell") == next(iter(rounds)),
        "release round count mismatch",
    )
    charts = artifacts.get("charts")
    _require(
        isinstance(charts, list) and len(charts) == 1, "chart artifact count mismatch"
    )


def _validate_article(
    article: str,
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    selection_input: Mapping[str, Any],
) -> None:
    rows = snapshot.get("rows")
    if not isinstance(rows, list) or len(rows) != 2:
        raise PublicationReproductionError("selection snapshot must contain two rows")
    policy = _mapping(manifest, "publication_policy")
    order = policy.get("display_order")
    if not isinstance(order, list) or [row["access_path_id"] for row in rows] != order:
        raise PublicationReproductionError("article display order drifted")
    _require(
        article.splitlines()[0] == "# Stock Quote API Test 2026: Finnhub vs EODHD",
        "article title drifted",
    )
    _require(
        "Neither tested Access Path qualified in this edition." in article,
        "article verdict drifted",
    )
    _require(
        "neither returned a quote that met the frozen contract in any of the "
        "four positive scenarios" in article,
        "article lead outcome drifted",
    )
    total_calls = sum(
        result["total_rounds"] for row in rows for result in row["case_results"]
    )
    _require(
        f"Across {total_calls} live calls" in article, "article call total drifted"
    )
    quick_rows = _markdown_table_rows(article, "| Provider | Tested Access Path |")
    if len(quick_rows) != len(rows):
        raise PublicationReproductionError("article result table row count drifted")
    for row, published in zip(rows, quick_rows, strict=True):
        results = {result["case_id"]: result for result in row["case_results"]}
        expected = [
            row["provider_name"],
            f"`{row['access_path_id']}` via QVeris",
            *[
                f"{results[case_id]['passed_rounds']}/{results[case_id]['total_rounds']}"
                for case_id in (
                    "aapl-quote",
                    "aapl-freshness-precision",
                    "cn-600519-market-coverage",
                    "cn-600519-agent-contract",
                    "invalid-stock",
                )
            ],
            "Not qualified",
        ]
        _require(
            published == expected, f"article result drifted: {row['provider_name']}"
        )
    reasons = {
        row["provider_id"]: {
            reason
            for result in row["case_results"]
            for reason in result["failure_reasons"]
        }
        for row in rows
    }
    _require(
        "stale_timestamp" in reasons["finnhub"]
        and "The tested Finnhub QVeris Access Path returned a stale timestamp"
        in article,
        "article reason drifted: Finnhub",
    )
    _require(
        "invalid_timestamp" in reasons["eodhd"]
        and "The tested EODHD QVeris Access Path returned an invalid timestamp"
        in article,
        "article reason drifted: EODHD",
    )
    _require(
        all(
            "unavailable_quote" in provider_reasons
            for provider_reasons in reasons.values()
        )
        and article.count("unavailable quotes") == 2,
        "article CN failure reason drifted",
    )
    pricing_rows = _markdown_table_rows(
        article, "| Provider | Official pricing observed in the registry |"
    )
    if len(pricing_rows) != len(rows):
        raise PublicationReproductionError("article pricing row count drifted")
    for row, published in zip(rows, pricing_rows, strict=True):
        pricing = row["official_pricing"]
        _require(pricing["state"] == "declared", "official pricing is unavailable")
        expected = [
            row["provider_name"],
            f"{pricing['free_tier']}; {pricing['paid_plans']}",
            "Not measured for this publication",
        ]
        _require(
            published == expected, f"article pricing drifted: {row['provider_name']}"
        )
    provenance = (
        f"GitHub Actions run `{snapshot['github_run_id']}` "
        f"on {snapshot['observation_date']}"
    )
    _require(
        provenance in article,
        "article observation provenance drifted",
    )
    _require(
        f"stores {total_calls} terminal cells and {total_calls} public evidence records"
        in article,
        "article evidence count drifted",
    )
    _require(
        "required `symbol`, a finite positive `price`, and an ISO 8601 timestamp "
        "no more than 900 seconds old" in article,
        "article positive contract drifted",
    )
    _require(
        "The negative control used `NOTASTOCK`." in article
        and "AAPL quote, AAPL timestamp freshness" in article
        and "representative CN quote for `600519.SH`" in article,
        "article case inputs drifted",
    )
    _require(
        "negative control required a non-empty validation error and prohibited "
        "invented quote fields" in article,
        "article negative contract drifted",
    )
    github_run = _mapping(selection_input, "github_run")
    _require(
        github_run.get("run_id") == snapshot["github_run_id"]
        and github_run.get("github_sha") == snapshot["github_sha"]
        and github_run.get("conclusion") == "success",
        "publication GitHub run metadata drifted",
    )
    _require(
        "Ranking their latency would reward fast failures" in article,
        "article latency boundary drifted",
    )
    sections = policy.get("required_sections")
    _require(
        isinstance(sections, list)
        and all(f"## {section}" in article for section in sections),
        "required article section is missing",
    )
    seo = _mapping(manifest, "seo")
    _require(
        seo.get("title") == article.splitlines()[0].removeprefix("# "),
        "SEO title drifted",
    )
    expected_meta = (
        f"Compare Finnhub and EODHD Stock Quote API paths using {total_calls} live "
        "calls, freshness checks, invalid-symbol controls, pricing, and "
        "reproducible evidence in 2026."
    )
    _require(seo.get("meta_description") == expected_meta, "SEO meta drifted")
    _require(
        40 <= len(str(seo.get("title"))) <= 60
        and 150 <= len(str(seo.get("meta_description"))) <= 160,
        "SEO metadata length drifted",
    )


def _validate_links(
    article: str,
    manifest: Mapping[str, Any],
    article_path: Path,
    repository_root: Path,
) -> None:
    seo = _mapping(manifest, "seo")
    expected = set(str(item) for item in seo.get("github_links", ()))
    official = seo.get("official_sources")
    if isinstance(official, Mapping):
        expected.update(str(value) for value in official.values())
    related = seo.get("related_guides")
    if isinstance(related, list):
        for item in related:
            if isinstance(item, Mapping):
                expected.add(str(item.get("url")))
                _require(
                    f"[{item.get('anchor')}]({item.get('url')})" in article,
                    "related guide anchor or URL drifted",
                )
    actual_external = [
        target
        for target in re.findall(r"\]\(([^)]+)\)", article)
        if target.startswith(("https://", "http://"))
    ]
    _require(
        set(actual_external) == expected and len(actual_external) == len(expected),
        "article external links differ from the allowlist",
    )
    for target in re.findall(r"\]\(([^)]+)\)", article):
        if target.startswith(("https://", "http://", "#", "mailto:")):
            continue
        resolved = (article_path.parent / target.split("#", 1)[0]).resolve()
        try:
            relative = resolved.relative_to(repository_root.resolve())
        except ValueError as exc:
            raise PublicationReproductionError(
                "article link must stay inside the repository"
            ) from exc
        resolve_repository_path(repository_root, str(relative))


def _validate_input_paths(document: Mapping[str, Any], repository_root: Path) -> None:
    for key in (
        "suite",
        "cases",
        "observation_schema",
        "binding_registry",
        "providers_root",
        "public_evidence_root",
    ):
        value = document.get(key)
        if not isinstance(value, str):
            raise PublicationReproductionError(
                f"selection input path is missing: {key}"
            )
        resolve_repository_path(repository_root, value)
    release = _mapping(document, "release")
    path = release.get("path")
    if not isinstance(path, str):
        raise PublicationReproductionError("selection input release path is missing")
    resolve_repository_path(repository_root, path)


def _markdown_table_rows(article: str, header: str) -> list[list[str]]:
    lines = article.splitlines()
    try:
        index = next(index for index, line in enumerate(lines) if header in line)
    except StopIteration as exc:
        raise PublicationReproductionError(
            f"article table is missing: {header}"
        ) from exc
    rows = []
    for line in lines[index + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def _mapping(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = document.get(key)
    if not isinstance(value, Mapping):
        raise PublicationReproductionError(
            f"publication field must be a mapping: {key}"
        )
    return value


def _artifact(repository_root: Path, artifacts: Mapping[str, Any], key: str) -> Path:
    value = artifacts.get(key)
    if not isinstance(value, str):
        raise PublicationReproductionError(f"missing publication artifact: {key}")
    return resolve_repository_path(repository_root, value)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublicationReproductionError(message)


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
