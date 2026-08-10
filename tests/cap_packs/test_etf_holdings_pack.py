from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from qveris_bench.catalog.validation import validate_cap_file
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.outcomes.evaluator import evaluate_outcome
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation
from qveris_bench.providers.repository import ProviderRegistryRepository
from qveris_bench.suites.bindings import (
    load_provider_bindings,
    validate_provider_bindings,
)
from qveris_bench.suites.compiler import compile_suite
from qveris_bench.suites.loader import load_cases, load_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs" / "etf_holdings"
PROVIDERS = ROOT / "providers"


def test_ac1_etf_holdings_pack_is_a_versioned_direct_benchmark() -> None:
    cap = validate_cap_file(PACK / "cap.yaml")
    suite = load_suite(PACK / "suite.yaml")
    cases = load_cases(PACK / "cases.yaml")

    assert (cap.cap_id, cap.version) == ("etf-holdings", "1.0.0")
    assert suite.cap_id == cap.cap_id
    assert suite.cap_version == cap.version
    assert suite.rounds >= 3
    assert [mode.value for mode in suite.modes] == ["direct"]
    assert {case.case_id for case in cases} == set(suite.case_ids)


def test_ac2_etf_holdings_pack_covers_success_and_negative_control() -> None:
    cases = {case.case_id: case for case in load_cases(PACK / "cases.yaml")}

    assert cases["spy-holdings"].input == {"symbol": "SPY"}
    assert not cases["spy-holdings"].negative_control
    assert "holdings" in cases["spy-holdings"].completion_conditions
    assert cases["qqq-holdings"].input == {"symbol": "QQQ"}
    assert cases["iwm-holdings"].input == {"symbol": "IWM"}
    assert cases["invalid-etf"].negative_control
    assert cases["invalid-etf"].completion_conditions == ("validation_error",)


def test_ac3_etf_holdings_bindings_are_distinct_attributable_direct_paths() -> None:
    data = yaml.safe_load((PACK / "provider-bindings.yaml").read_text())
    bindings = data["access_paths"]

    assert len(bindings) == 2
    assert len({binding["provider_id"] for binding in bindings}) == len(bindings)
    assert len({binding["access_path_id"] for binding in bindings}) == len(bindings)
    assert all(
        binding["official_source"].startswith("https://") for binding in bindings
    )


def test_ac3_cohort_includes_only_qveris_attributable_direct_paths() -> None:
    records = ProviderRegistryRepository(PROVIDERS).cohort_check()
    paths = {
        path.access_path_id: path for record in records for path in record.access_paths
    }
    suite = load_suite(PACK / "suite.yaml")

    etf_candidates = {
        record.provider_id
        for record in records
        if any("etf-holdings" in path.access_path_id for path in record.access_paths)
    }
    assert etf_candidates == {
        "alpha-vantage",
        "eodhd",
        "financial-modeling-prep",
        "finnhub",
        "fiu",
        "twelve-data",
    }

    assert all(
        paths[path_id].qualification is not None for path_id in suite.access_path_ids
    )
    assert set(suite.access_path_ids) == {
        "alpha-vantage-etf-holdings",
        "fiu-etf-holdings",
    }
    assert all(
        paths[path_id].qualification.disposition.value == "included"
        for path_id in suite.access_path_ids
    )
    assert all(
        paths[path_id].provider_id != "qveris-finance"
        for path_id in suite.access_path_ids
    )
    validate_provider_bindings(
        load_provider_bindings(PACK / "provider-bindings.yaml"),
        tuple(paths[path_id] for path_id in suite.access_path_ids),
    )
    compiled = compile_suite(PACK / "suite.yaml", PACK / "cases.yaml", PROVIDERS)
    assert len(compiled.run_plan.cells) == 24


def test_ac3_twelve_data_exclusion_references_direct_diagnostic_evidence() -> None:
    records = ProviderRegistryRepository(PROVIDERS).cohort_check()
    twelve_data = next(
        record for record in records if record.provider_id == "twelve-data"
    )
    path = next(
        path
        for path in twelve_data.access_paths
        if path.access_path_id == "twelve-data-etf-holdings"
    )
    evidence_path = ROOT / "docs/evidence/qveris-direct-diagnostic-2026-08-06.json"

    assert path.qualification is not None
    assert path.qualification.disposition.value == "excluded"
    assert path.qualification.evidence_digest == sha256_digest(
        evidence_path.read_bytes()
    )


def test_ac4_etf_holdings_rules_describe_facts_not_scores() -> None:
    observation_schema = yaml.safe_load((PACK / "observation-schema.yaml").read_text())
    outcome_rules = yaml.safe_load((PACK / "outcome-rules.yaml").read_text())

    assert observation_schema["required_fields"] == ["symbol", "holdings", "weights"]
    assert outcome_rules["completion_requires"] == ["symbol", "holdings", "weights"]
    text = (PACK / "outcome-rules.yaml").read_text().lower()
    assert "score" not in text


def test_ac5_etf_observation_requires_weighted_holdings_or_an_error_fact() -> None:
    observation = extract_observation(
        PACK / "observation-schema.yaml",
        {"symbol": "SPY", "holdings": ["AAPL"], "weights": [0.07]},
        "sha256:" + "a" * 64,
        "1.0.0",
    )
    outcome = evaluate_outcome(
        ("symbol", "holdings", "weights"), observation.facts, observation.evidence_ref
    )
    assert outcome.unmet_conditions == ()
    with pytest.raises(ExtractionError, match="weights"):
        extract_observation(
            PACK / "observation-schema.yaml",
            {"symbol": "SPY", "holdings": ["AAPL"]},
            "sha256:" + "a" * 64,
            "1.0.0",
        )
    with pytest.raises(ExtractionError, match="unaligned"):
        extract_observation(
            PACK / "observation-schema.yaml",
            {"symbol": "SPY", "holdings": ["AAPL", "MSFT"], "weights": [0.07]},
            "sha256:" + "a" * 64,
            "1.0.0",
        )
    error = extract_observation(
        PACK / "observation-schema.yaml",
        {"validation_error": "unknown ETF"},
        "sha256:" + "a" * 64,
        "1.0.0",
        negative_control=True,
    )
    assert error.facts == {"validation_error": "unknown ETF"}
