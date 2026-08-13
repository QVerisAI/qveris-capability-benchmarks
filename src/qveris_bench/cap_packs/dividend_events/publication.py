from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageChops

from qveris_bench.models.publication import PublicationPackageSpec
from qveris_bench.profiles.selection import build_selection_snapshot
from qveris_bench.publications.service import (
    PublicationReproductionError,
    resolve_repository_path,
)
from qveris_bench.yaml_io import load_yaml_mapping

_PROVIDER_NAMES = {
    "hangseng": "Hang Seng",
    "ifind": "iFinD",
    "alpha-vantage": "Alpha Vantage",
    "twelve-data": "Twelve Data",
    "eodhd": "EODHD",
    "massive-stocks": "Massive",
}
_MANIFEST_PROVIDER_NAMES = {
    "hangseng": "恒生聚源",
    "ifind": "同花顺 iFinD",
    "alpha-vantage": "Alpha Vantage",
    "twelve-data": "Twelve Data",
    "eodhd": "EODHD",
    "massive-stocks": "Massive",
}
_MARKET_ORDER = ("US", "HK", "CN", "JP", "DE", "FR", "BR", "IN", "ES")
_NUMBER_WORDS = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


class DividendEventsPublicationAdapter:
    adapter_id = "dividend-events-v1"
    adapter_version = "1.0.0"
    cap_id = "dividend-events"

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
        if package.release_sections != ("release", "market_coverage_release"):
            raise PublicationReproductionError(
                "Dividend publication requires baseline and market Releases exactly"
            )
        artifacts = _mapping(document, "artifacts")
        snapshot_input = _artifact(
            repository_root, artifacts, "selection_snapshot_input"
        )
        committed_snapshot = _artifact(repository_root, artifacts, "selection_snapshot")
        selection_input_document = load_yaml_mapping(snapshot_input)
        _validate_selection_paths(selection_input_document, repository_root)
        _validate_selection_release_refs(selection_input_document, document)
        fresh_snapshot = build_selection_snapshot(snapshot_input, repository_root)
        if fresh_snapshot.json_bytes != committed_snapshot.read_bytes():
            raise PublicationReproductionError(
                "selection snapshot differs from a fresh release-derived build"
            )

        chart_dir = output_dir / "charts"
        generated = _render_selection_tradeoff(
            committed_snapshot,
            chart_dir,
            output_dir,
        )
        committed_chart_manifest = _artifact(
            repository_root, artifacts, "selection_charts_manifest"
        )
        expected_manifest_digest = artifacts.get("selection_charts_manifest_digest")
        if expected_manifest_digest != _digest(committed_chart_manifest.read_bytes()):
            raise PublicationReproductionError(
                "selection chart manifest digest mismatch"
            )
        committed = json.loads(committed_chart_manifest.read_text(encoding="utf-8"))
        for field in ("data", "input_digests", "rendered_at", "renderer"):
            if generated[field] != committed[field]:
                raise PublicationReproductionError(
                    f"chart {field} differs from the committed chart manifest"
                )
        charts = artifacts.get("charts")
        if not isinstance(charts, list) or not charts:
            raise PublicationReproductionError("publication charts must be declared")
        declared_chart_names = {
            Path(value).name for value in charts if isinstance(value, str)
        }
        committed_charts = _mapping(committed, "charts")
        generated_charts = _mapping(generated, "charts")
        committed_chart_names = set(committed_charts)
        generated_chart_names = set(generated_charts)
        if not (
            declared_chart_names == committed_chart_names == generated_chart_names
            and len(declared_chart_names) == len(charts)
        ):
            raise PublicationReproductionError(
                "declared, committed, and generated chart sets must match"
            )
        for chart_value in charts:
            if not isinstance(chart_value, str):
                raise PublicationReproductionError("invalid publication chart path")
            committed_chart = resolve_repository_path(repository_root, chart_value)
            expected = committed_charts.get(committed_chart.name)
            if expected != _digest(committed_chart.read_bytes()):
                raise PublicationReproductionError(
                    f"committed chart digest mismatch: {committed_chart.name}"
                )
            generated_chart = chart_dir / committed_chart.name
            if not _same_chart_pixels(generated_chart, committed_chart):
                raise PublicationReproductionError(
                    f"canonical chart pixels differ: {committed_chart.name}"
                )
            if platform.system() == "Linux" and (
                generated_chart.read_bytes() != committed_chart.read_bytes()
            ):
                raise PublicationReproductionError(
                    f"canonical chart bytes differ: {committed_chart.name}"
                )

        snapshot = json.loads(committed_snapshot.read_text(encoding="utf-8"))
        if snapshot.get("cap_id") != package.cap_id:
            raise PublicationReproductionError(
                "publication package CAP does not match the Selection Snapshot"
            )
        _validate_manifest_metadata(
            document,
            artifacts,
            snapshot_input,
            committed_snapshot,
            repository_root,
        )
        article = _artifact(repository_root, artifacts, "article")
        article_text = article.read_text(encoding="utf-8")
        article_facts_path = _artifact(repository_root, artifacts, "article_facts")
        article_facts = _build_article_facts(snapshot, document, repository_root)
        expected_article_facts = _canonical_json(article_facts)
        if article_facts_path.read_bytes() != expected_article_facts:
            raise PublicationReproductionError(
                "article facts differ from fresh release-derived facts"
            )
        if artifacts.get("article_facts_digest") != _digest(expected_article_facts):
            raise PublicationReproductionError("article facts digest mismatch")
        _validate_article_facts(
            article_text,
            snapshot,
            document,
            repository_root,
            article_facts,
        )
        _validate_links(article_text, document, article, repository_root)
        return ("selection_snapshot", "charts", "article_facts", "links")


def _render_selection_tradeoff(
    snapshot: Path,
    chart_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    cache_dir = output_dir / "matplotlib-cache"
    cache_dir.mkdir()
    previous = {
        name: os.environ.get(name) for name in ("MPLCONFIGDIR", "XDG_CACHE_HOME")
    }
    os.environ["MPLCONFIGDIR"] = str(cache_dir)
    os.environ["XDG_CACHE_HOME"] = str(cache_dir)
    try:
        from qveris_bench.cap_packs.dividend_events.selection_charts import (
            render_selection_tradeoff,
        )

        return render_selection_tradeoff(snapshot, chart_dir)
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _same_chart_pixels(generated: Path, committed: Path) -> bool:
    with (
        Image.open(generated) as generated_image,
        Image.open(committed) as committed_image,
    ):
        left = generated_image.convert("RGBA")
        right = committed_image.convert("RGBA")
        return (
            left.size == right.size
            and ImageChops.difference(left, right).getbbox() is None
        )


def _build_article_facts(
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, object]:
    rows = snapshot.get("rows")
    if not isinstance(rows, list) or not rows:
        raise PublicationReproductionError("selection snapshot has no rows")
    baseline = _release_article_facts(manifest, "release", repository_root)
    market = _release_article_facts(
        manifest,
        "market_coverage_release",
        repository_root,
    )
    baseline_dates = {
        str(_mapping(row, "observation_window").get("end")) for row in rows
    }
    market_dates = {
        str(_mapping(row, "market_coverage").get("observation_date")) for row in rows
    }
    if len(baseline_dates) != 1 or len(market_dates) != 1:
        raise PublicationReproductionError(
            "article facts require one observation date per Release"
        )
    markets = {
        str(result["market"])
        for row in rows
        for result in _mapping(row, "market_coverage")["results"]
    }
    if markets != set(_MARKET_ORDER):
        raise PublicationReproductionError("article facts market set drifted")
    measured_rows = [
        row
        for row in rows
        if _mapping(row, "gateway_metrics").get("state") == "measured"
    ]
    latency_sample_sizes = {
        int(_mapping(row, "gateway_metrics")["latency_sample_size"])
        for row in measured_rows
    }
    pricing_dates = {
        str(_mapping(row, "qveris_list_price")["inspected_at"]) for row in measured_rows
    }
    if len(latency_sample_sizes) != 1 or len(pricing_dates) != 1:
        raise PublicationReproductionError(
            "article facts require one runtime sample size and pricing date"
        )
    return {
        "schema_version": 1,
        "package_id": _mapping(manifest, "publication_package")["package_id"],
        "edition": str(manifest["edition"]),
        "provider_count": len({str(row["provider_id"]) for row in rows}),
        "access_path_count": len(rows),
        "qveris_access_path_count": len(measured_rows),
        "latency_sample_size": latency_sample_sizes.pop(),
        "pricing_observed_at": pricing_dates.pop(),
        "markets": list(_MARKET_ORDER),
        "total_live_calls": cast(int, baseline["public_evidence_records"])
        + cast(int, market["public_evidence_records"]),
        "baseline_release": {
            **baseline,
            "observation_date": baseline_dates.pop(),
        },
        "market_release": {
            **market,
            "observation_date": market_dates.pop(),
        },
    }


def _release_article_facts(
    manifest: Mapping[str, Any],
    section_key: str,
    repository_root: Path,
) -> dict[str, object]:
    metadata = _mapping(manifest, section_key)
    release_path = resolve_repository_path(
        repository_root,
        f"{metadata['directory']}/release.json",
    )
    release = json.loads(release_path.read_text(encoding="utf-8"))
    cells = release["cells"]
    applicable = [cell for cell in cells if cell["applicable"]]
    combinations = {
        (cell["provider_id"], cell["access_path_id"], cell["case_id"])
        for cell in applicable
    }
    return {
        "release_id": release["release"]["release_id"],
        "release_digest": metadata["digest"],
        "planned_cells": len(cells),
        "applicable_cells": len(applicable),
        "not_applicable_cells": len(cells) - len(applicable),
        "public_evidence_records": len(release["evidence"]),
        "rounds_per_cell": len({cell["round"] for cell in applicable}),
        "positive_case_cells": sum("invalid" not in item[2] for item in combinations),
        "negative_control_cells": sum("invalid" in item[2] for item in combinations),
    }


def _canonical_json(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def _format_article_date(value: object) -> str:
    parsed = date.fromisoformat(str(value))
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def _number_word(value: int) -> str:
    return _NUMBER_WORDS.get(value, str(value))


def _round_phrase(value: int) -> str:
    if value == 1:
        return "once"
    if value == 2:
        return "twice"
    return f"{_number_word(value)} times"


def _validate_material_claims(
    article: str,
    facts: Mapping[str, Any],
) -> None:
    baseline = _mapping(facts, "baseline_release")
    market = _mapping(facts, "market_release")
    markets = facts["markets"]
    if not isinstance(markets, list):
        raise PublicationReproductionError("article facts markets must be a list")
    market_list = ", ".join(str(value) for value in markets[:-1])
    market_list += f", and {markets[-1]}"
    access_path_count = int(facts["access_path_count"])
    market_count = len(markets)
    baseline_date = _format_article_date(baseline["observation_date"])
    market_date = _format_article_date(market["observation_date"])
    access_path_word = _number_word(access_path_count)
    claims = (
        (
            f"We made {facts['total_live_calls']} live calls across two test suites, "
            "including invalid-symbol controls and representative symbols from "
            f"{market_list}. These **representative market sample results** are not "
            "claims about every security, date range, entitlement, or market a "
            "provider covers."
        ),
        (
            f"The baseline test ran on {baseline_date}. "
            "Each applicable Access Path had one positive security sample and one "
            "invalid-symbol negative control, each repeated "
            f"{_round_phrase(int(baseline['rounds_per_cell']))}: "
            f"{baseline['public_evidence_records']} live calls. The market test ran "
            f"on {market_date}. It included "
            f"{market['positive_case_cells']} applicable positive cells plus one "
            f"negative control for each of the {access_path_word} paths, "
            f"repeated {_round_phrase(int(market['rounds_per_cell']))}: "
            f"{market['public_evidence_records']} live calls. The two Releases remain "
            "separate and are not combined into a score."
        ),
        (
            "The market Release contains "
            f"{market['planned_cells']} planned test cells. "
            f"All {market['applicable_cells']} applicable cells have sanitized public "
            f"evidence, while the other {market['not_applicable_cells']} retain an "
            "explicit not-applicable reason. Unknown states, temporary failures, and "
            "missing evidence cannot be relabeled as not applicable."
        ),
        (
            f"The package pins the baseline Release `{baseline['release_id']}` at "
            f"`{baseline['release_digest']}` and the market Release "
            f"`{market['release_id']}` at `{market['release_digest']}`; the same "
            "command verifies both."
        ),
    )
    for index, claim in enumerate(claims, start=1):
        if article.count(claim) != 1:
            raise PublicationReproductionError(
                f"article facts drifted: material claim {index}"
            )
    latency_samples = int(facts["latency_sample_size"])
    latency_word = _number_word(latency_samples)
    qveris_path_count = int(facts["qveris_access_path_count"])
    qveris_path_word = _number_word(qveris_path_count)
    snippets = (
        f"across {latency_word} calls",
        f"{latency_word.title()} calls can prioritize a reproduction test",
        f"A {latency_word}-call median is not a Native API performance ranking or SLA.",
        "- **Baseline repeatability:** "
        f"{_number_word(int(baseline['rounds_per_cell']))} rounds per applicable case; "
        "Direct Test is mandatory.",
        "- **Market extension:** one representative symbol for each of "
        f"{_number_word(market_count)} markets, with "
        f"{_number_word(int(market['rounds_per_cell']))} rounds per applicable cell.",
        f"runs {_number_word(int(baseline['rounds_per_cell']))} baseline rounds.",
        f"runs {_number_word(int(market['rounds_per_cell']))} rounds for each "
        "applicable market binding:",
        f"- {qveris_path_word} QVeris Access Paths use `QVERIS_API_KEY`;",
        "QVeris credits are the public Inspect prices observed on "
        f"{_format_article_date(facts['pricing_observed_at'])};",
    )
    for snippet in snippets:
        if article.count(snippet) != 1:
            raise PublicationReproductionError("article facts drifted")
    _require(
        market_count == 9,
        "article facts market count drifted",
    )


def _validate_selection_release_refs(
    selection_input: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    expected = (
        ("cap_release", "release"),
        ("market_coverage_release", "market_coverage_release"),
    )
    for input_key, manifest_key in expected:
        selection_ref = _mapping(selection_input, input_key)
        manifest_ref = _mapping(manifest, manifest_key)
        expected_release = f"{manifest_ref['directory']}/release.json"
        if selection_ref.get("release") != expected_release or (
            selection_ref.get("digest") != manifest_ref.get("digest")
        ):
            raise PublicationReproductionError(
                f"selection input release differs from {manifest_key}"
            )


def _validate_selection_paths(
    selection_input: Mapping[str, Any],
    repository_root: Path,
) -> None:
    direct_paths = ("suite", "cases", "providers_root")
    nested_paths = (
        ("cap_release", "release"),
        ("qveris_list_pricing", "snapshot"),
        ("qveris_list_pricing", "bindings"),
        ("official_pricing_supplement", "snapshot"),
        ("market_coverage_release", "release"),
        ("market_coverage_release", "suite"),
        ("market_coverage_release", "cases"),
    )
    for key in direct_paths:
        value = selection_input.get(key)
        if not isinstance(value, str):
            raise PublicationReproductionError(
                f"selection input path is missing: {key}"
            )
        resolve_repository_path(repository_root, value)
    for section, key in nested_paths:
        value = _mapping(selection_input, section).get(key)
        if not isinstance(value, str):
            raise PublicationReproductionError(
                f"selection input path is missing: {section}.{key}"
            )
        resolve_repository_path(repository_root, value)


def _validate_manifest_metadata(
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    snapshot_input: Path,
    snapshot: Path,
    repository_root: Path,
) -> None:
    snapshot_document = json.loads(snapshot.read_text(encoding="utf-8"))
    _require(
        str(manifest.get("edition")) == snapshot_document.get("edition"),
        "publication edition mismatch",
    )
    snapshot_metadata = _mapping(manifest, "selection_snapshot")
    _require(
        snapshot_metadata.get("id") == snapshot_document.get("snapshot_id"),
        "selection snapshot identity mismatch",
    )
    _require(
        snapshot_metadata.get("input_digest") == _digest(snapshot_input.read_bytes()),
        "selection snapshot input digest mismatch",
    )
    _require(
        snapshot_metadata.get("digest") == _digest(snapshot.read_bytes()),
        "selection snapshot digest mismatch",
    )
    for section_key, artifact_key in (
        ("qveris_list_pricing", "qveris_list_pricing"),
        ("official_pricing_supplement", "official_pricing_supplement"),
    ):
        metadata = _mapping(manifest, section_key)
        artifact = _artifact(repository_root, artifacts, artifact_key)
        artifact_document = json.loads(artifact.read_text(encoding="utf-8"))
        _require(
            metadata.get("digest") == _digest(artifact.read_bytes()),
            f"{section_key} digest mismatch",
        )
        _require(
            metadata.get("id") == artifact_document.get("snapshot_id")
            and metadata.get("source") == artifact_document.get("source"),
            f"{section_key} identity or source mismatch",
        )
        if section_key == "qveris_list_pricing":
            _require(
                metadata.get("inspected_at") == artifact_document.get("inspected_at"),
                "qveris_list_pricing inspection date mismatch",
            )
    for section_key in ("release", "market_coverage_release"):
        metadata = _mapping(manifest, section_key)
        release_path = resolve_repository_path(
            repository_root,
            f"{metadata['directory']}/release.json",
        )
        release = json.loads(release_path.read_text(encoding="utf-8"))
        release_metadata = release["release"]
        cells = release["cells"]
        _require(
            metadata.get("suite_fingerprint")
            == release_metadata.get("suite_fingerprint"),
            f"{section_key} suite fingerprint mismatch",
        )
        _require(
            metadata.get("planned_cells") == len(cells),
            f"{section_key} planned cell count mismatch",
        )
        _require(
            metadata.get("applicable_cells")
            == sum(bool(cell["applicable"]) for cell in cells),
            f"{section_key} applicable cell count mismatch",
        )
        _require(
            metadata.get("public_evidence_records") == len(release["evidence"]),
            f"{section_key} public evidence count mismatch",
        )
        if section_key == "market_coverage_release":
            applicable = [cell for cell in cells if cell["applicable"]]
            rounds = {cell["round"] for cell in applicable}
            _require(
                metadata.get("rounds_per_cell") == len(rounds),
                "market_coverage_release round count mismatch",
            )


def _validate_article_facts(
    article: str,
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    repository_root: Path,
    article_facts: Mapping[str, Any],
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
    agent = _markdown_table_rows(
        article,
        "| Provider and Access Path | Required event fields |",
    )
    expected_identities = [
        (
            _PROVIDER_NAMES[str(row["provider_id"])],
            "Native MCP" if row["access_path_type"] == "native_mcp" else "QVeris",
        )
        for row in ordered_rows
    ]
    for table in (overview, pricing, market, agent):
        published_identities = [_row_identity(table_row[0]) for table_row in table]
        if published_identities != expected_identities:
            raise PublicationReproductionError(
                "article Provider and Access Path identity drifted"
            )

    for row in ordered_rows:
        provider = _PROVIDER_NAMES[str(row["provider_id"])]
        access = "Native MCP" if row["access_path_type"] == "native_mcp" else "QVeris"
        overview_row = _provider_row(overview, provider, access)
        _require(
            overview_row[1] == _expected_overview_outcome(row),
            f"baseline outcome drifted: {provider}",
        )
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

        agent_row = _provider_row(agent, provider, access)
        expected_agent = _agent_expected_cells(
            row,
            manifest,
            repository_root,
        )
        invalid = row["agent_interface"]["invalid_input_handling"]
        expected_invalid = f"Handled correctly {invalid['passed']}/{invalid['total']}"
        _require(
            agent_row[1:]
            == [
                expected_agent[0],
                expected_agent[1],
                expected_invalid,
                expected_agent[2],
                expected_agent[3],
            ],
            f"Agent facts drifted: {provider}",
        )

    _validate_material_claims(article, article_facts)
    seo = _mapping(manifest, "seo")
    provider_count = int(article_facts["provider_count"])
    access_path_count = int(article_facts["access_path_count"])
    market_count = len(article_facts["markets"])
    _require(
        seo.get("title")
        == f"Best Dividend APIs for Developers in 2026: {provider_count} Providers",
        "SEO title drifted",
    )
    _require(
        seo.get("meta_description")
        == (
            f"Compare {access_path_count} dividend API Access Paths using "
            f"{article_facts['total_live_calls']} live calls: event fields, "
            "invalid-symbol handling, QVeris pricing, "
            f"{_number_word(market_count)} markets, and reproducible evidence."
        ),
        "SEO meta description drifted",
    )
    _require(
        article.splitlines()[0]
        == f"# Best Dividend APIs for Developers in 2026: {len(rows)} Providers",
        "article title Provider count drifted",
    )
    by_provider = {row["provider_id"]: row for row in rows}
    quick_advice = article.split("> **Quick recommendation:** ", 1)[1].split("\n", 1)[0]
    eodhd_verified = _verified_markets(by_provider["eodhd"])
    twelve_verified = _verified_markets(by_provider["twelve-data"])
    alpha_results = by_provider["alpha-vantage"]["market_coverage"]["results"]
    alpha_verified = _verified_markets(by_provider["alpha-vantage"])
    alpha_not_applicable = sum(
        result["state"] == "not_applicable" for result in alpha_results
    )
    expected_quick_advice = (
        "Through the tested QVeris Access Paths, start by reproducing Alpha "
        "Vantage, Twelve Data, EODHD, or Massive for basic US Dividend Events. "
        "For broader representative-market results, "
        f"EODHD passed {eodhd_verified} markets and Twelve Data passed "
        f"{twelve_verified}. Alpha Vantage passed all {alpha_verified} markets "
        "that QVeris marked applicable; we did not spend calls retesting the "
        f"other {alpha_not_applicable} explicitly unsupported markets."
    )
    _require(
        quick_advice == expected_quick_advice,
        "quick recommendation drifted",
    )
    measured = [row for row in rows if row["gateway_metrics"]["state"] == "measured"]
    fastest = min(
        measured,
        key=lambda row: row["gateway_metrics"]["latency_median_ms"],
    )
    _require(
        f"{_PROVIDER_NAMES[fastest['provider_id']]} had the lowest median latency"
        in article,
        "latency ranking drifted",
    )
    minimum_price = min(row["qveris_list_price"]["amount_credits"] for row in measured)
    lowest_price_names = sorted(
        _PROVIDER_NAMES[row["provider_id"]]
        for row in measured
        if row["qveris_list_price"]["amount_credits"] == minimum_price
    )
    _require(
        f"{_english_list(lowest_price_names)} shared the lowest Inspect price at "
        f"{minimum_price:g} credit/call" in article,
        "price ranking drifted",
    )


def _validate_links(
    article: str,
    manifest: Mapping[str, Any],
    article_path: Path,
    repository_root: Path,
) -> None:
    seo = _mapping(manifest, "seo")
    allowed_github = seo.get("github_links")
    actual = re.findall(r"\]\((https://github\.com/[^)]+)\)", article)
    _require(
        actual == allowed_github,
        "article GitHub links differ from the allowlist",
    )
    allowed_external = set(actual)
    for key in ("supplier_sites", "provider_pages", "official_sources"):
        values = seo.get(key, {})
        if isinstance(values, Mapping):
            allowed_external.update(
                value for value in values.values() if isinstance(value, str)
            )
    related = seo.get("related_guides", [])
    if isinstance(related, list):
        allowed_external.update(
            item["url"]
            for item in related
            if isinstance(item, Mapping) and isinstance(item.get("url"), str)
        )
        for item in related:
            if isinstance(item, Mapping):
                _require(
                    f"[{item.get('anchor')}]({item.get('url')})" in article,
                    "related guide anchor or URL drifted",
                )
    artifacts = _mapping(manifest, "artifacts")
    snapshot_path = _artifact(repository_root, artifacts, "selection_snapshot")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    allowed_external.update(
        row["official_pricing"]["pricing_url"]
        for row in snapshot["rows"]
        if row["official_pricing"]["state"] == "declared"
    )
    local_chart_paths = artifacts.get("charts")
    if not isinstance(local_chart_paths, list):
        raise PublicationReproductionError("publication charts must be declared")
    allowed_local = {
        resolve_repository_path(repository_root, value)
        for value in local_chart_paths
        if isinstance(value, str)
    }
    overview = _markdown_table_rows(article, "| Provider and Access Path |")
    supplier_sites = _mapping(seo, "supplier_sites")
    provider_pages = _mapping(seo, "provider_pages")
    for row in snapshot["rows"]:
        provider_id = row["provider_id"]
        provider = _PROVIDER_NAMES[provider_id]
        access = "Native MCP" if row["access_path_type"] == "native_mcp" else "QVeris"
        article_row = _provider_row(overview, provider, access)
        manifest_name = _MANIFEST_PROVIDER_NAMES[provider_id]
        _require(
            f"]({supplier_sites[manifest_name]})" in article_row[0],
            f"supplier link drifted: {provider}",
        )
        if access == "QVeris":
            _require(
                f"]({provider_pages[manifest_name]})" in article_row[0],
                f"QVeris CTA drifted: {provider}",
            )
    for target in re.findall(r"\]\(([^)]+)\)", article):
        if target.startswith(("https://", "http://")):
            _require(
                target in allowed_external, f"external link is not allowed: {target}"
            )
            continue
        if target.startswith("#"):
            continue
        if target.startswith("mailto:"):
            raise PublicationReproductionError("article mail links are not allowed")
        resolved = (article_path.parent / target.split("#", 1)[0]).resolve()
        try:
            relative = resolved.relative_to(repository_root.resolve())
        except ValueError as exc:
            raise PublicationReproductionError(
                "article link must stay inside the repository"
            ) from exc
        resolved = resolve_repository_path(repository_root, str(relative))
        _require(resolved in allowed_local, "article local link is not declared")
    for target in re.findall(r"(?:https?://|mailto:)[^\s)<]+", article):
        normalized = target.rstrip(".,;")
        _require(
            normalized in allowed_external,
            f"external link is not allowed: {normalized}",
        )


def _expected_overview_outcome(row: Mapping[str, Any]) -> str:
    provider_id = row["provider_id"]
    if provider_id == "hangseng":
        return (
            "**CN sample passed:** both rounds returned a verifiable security "
            "identity, ex-dividend date, and single-event amount"
        )
    if provider_id == "ifind":
        return (
            "**Sample did not pass:** no single-event date, and the annual "
            "cumulative value cannot establish the amount for one event"
        )
    if provider_id == "twelve-data":
        return (
            "**Sample passed:** AAPL returned an ex-dividend date and single-event "
            "amount in all three rounds; the invalid symbol produced no fabricated "
            "event"
        )
    return (
        "**Sample passed:** both the AAPL sample and invalid-symbol control met "
        "the contract in all three rounds"
    )


def _verified_markets(row: Mapping[str, Any]) -> int:
    return sum(
        result["state"] == "verified" for result in row["market_coverage"]["results"]
    )


def _english_list(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return " and ".join(values)
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _agent_expected_cells(
    row: Mapping[str, Any],
    manifest: Mapping[str, Any],
    repository_root: Path,
) -> tuple[str, str, str, str]:
    provider_id = str(row["provider_id"])
    access_path_id = str(row["access_path_id"])
    section_key = "market_coverage_release" if provider_id == "hangseng" else "release"
    release = _mapping(manifest, section_key)
    release_dir = resolve_repository_path(repository_root, str(release["directory"]))
    evidence_manifest = json.loads(
        (release_dir / "public-evidence-manifest.json").read_text(encoding="utf-8")
    )
    entries = evidence_manifest.get("evidence")
    if not isinstance(entries, list):
        raise PublicationReproductionError("public evidence manifest is invalid")
    terminals = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise PublicationReproductionError("public evidence manifest is invalid")
        run_key = entry.get("run_key")
        relative_path = entry.get("path")
        public_digest = entry.get("public_digest")
        if not all(
            isinstance(value, str) for value in (run_key, relative_path, public_digest)
        ):
            raise PublicationReproductionError("public evidence manifest is invalid")
        run_key_text = str(run_key)
        is_cn_market_sample = ":cn-600519-dividend-market:" in run_key_text
        if (
            f":{provider_id}:{access_path_id}:direct:" not in run_key_text
            or "invalid" in run_key_text
            or (provider_id == "hangseng" and not is_cn_market_sample)
        ):
            continue
        path = resolve_repository_path(repository_root, str(relative_path))
        if _digest(path.read_bytes()) != public_digest:
            raise PublicationReproductionError("public evidence digest mismatch")
        terminal = json.loads(path.read_text(encoding="utf-8"))
        if (
            terminal.get("provider_id") != provider_id
            or terminal.get("access_path_id") != access_path_id
            or terminal.get("run_key") != run_key_text
        ):
            raise PublicationReproductionError(
                "public evidence Provider, Access Path, or run key mismatch"
            )
        terminals.append(terminal)
    if not terminals:
        raise PublicationReproductionError(
            f"no public terminal facts for {provider_id}"
        )
    completed = sum(item["state"] == "completed" for item in terminals)
    total = len(terminals)
    facts = [item["facts"] for item in terminals]
    required = (
        f"CN sample {completed}/{total}"
        if provider_id == "hangseng"
        else (
            "Missing single-event amount meaning and ex-dividend date"
            if completed == 0
            else f"{completed}/{total}"
        )
    )
    if all(item.get("identity_verified") is True for item in facts):
        identity = "Returned security code matched the requested symbol"
    elif provider_id == "ifind":
        identity = "No response security code was available to cross-check"
    else:
        identity = (
            "Published sample does not prove the response identified "
            f"`{facts[0]['symbol']}`"
        )
    currencies = {item.get("currency") for item in facts} - {None}
    if currencies:
        if len(currencies) != 1:
            raise PublicationReproductionError(
                f"inconsistent response currencies for {provider_id}"
            )
        currency = f"`{currencies.pop()}`"
    else:
        currency = (
            "Not published in this sample"
            if provider_id == "ifind"
            else "Not returned in this sample"
        )
    extra_fields = {"declaration_date", "record_date", "payment_date"}
    if all(extra_fields <= item.keys() for item in facts):
        dates = "Declaration, record, and payment dates"
    elif completed == 0:
        dates = "No single-event date set"
    else:
        dates = "Only ex-dividend date in this sample"
    return required, identity, currency, dates


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
    matches = [row for row in rows if _row_identity(row[0]) == (provider, access)]
    if len(matches) != 1:
        raise PublicationReproductionError(
            f"article must contain one row for {provider} / {access}"
        )
    return matches[0]


def _row_identity(cell: str) -> tuple[str, str]:
    visible = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cell).split(" · ", 1)[0]
    match = re.fullmatch(
        r"(?P<provider>.+?) (?:\((?P<paren>QVeris|Native MCP)\)|/ "
        r"(?P<slash>QVeris|Native MCP))",
        visible,
    )
    if match is None:
        raise PublicationReproductionError(
            "article Provider and Access Path identity drifted"
        )
    return match.group("provider"), match.group("paren") or match.group("slash")


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
