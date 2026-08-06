from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from qveris_bench.catalog.validation import validate_cap_file
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
PACK = ROOT / "cap_packs" / "stock_quote"
PROVIDERS = ROOT / "providers"


def test_ac1_stock_quote_pack_reuses_the_versioned_direct_contract() -> None:
    cap = validate_cap_file(PACK / "cap.yaml")
    suite = load_suite(PACK / "suite.yaml")
    cases = load_cases(PACK / "cases.yaml")

    assert (cap.cap_id, cap.version) == ("stock-quote", "1.0.0")
    assert suite.cap_id == cap.cap_id
    assert suite.cap_version == cap.version
    assert [mode.value for mode in suite.modes] == ["direct"]
    assert suite.access_path_ids == ("finnhub-stock-quote",)
    assert {case.case_id for case in cases} == set(suite.case_ids)


def test_ac2_stock_quote_pack_has_success_and_negative_control() -> None:
    cases = {case.case_id: case for case in load_cases(PACK / "cases.yaml")}

    assert cases["aapl-quote"].input == {"symbol": "AAPL"}
    assert cases["aapl-quote"].completion_conditions == ("symbol", "price", "timestamp")
    assert cases["invalid-stock"].negative_control
    assert cases["invalid-stock"].completion_conditions == ("validation_error",)


def test_ac3_stock_quote_binding_is_the_single_attributable_direct_candidate() -> None:
    data = yaml.safe_load((PACK / "provider-bindings.yaml").read_text())
    bindings = data["access_paths"]

    assert bindings == [
        {
            "access_path_id": "finnhub-stock-quote",
            "provider_id": "finnhub",
            "canonical_interface": "quote",
            "official_source": "https://finnhub.io/docs/api/quote",
        }
    ]


def test_ac3_stock_quote_direct_candidate_is_included_and_compiles() -> None:
    records = ProviderRegistryRepository(PROVIDERS).cohort_check()
    paths = {
        path.access_path_id: path for record in records for path in record.access_paths
    }
    suite = load_suite(PACK / "suite.yaml")

    assert paths["finnhub-stock-quote"].qualification.disposition.value == "included"
    validate_provider_bindings(
        load_provider_bindings(PACK / "provider-bindings.yaml"),
        tuple(paths[path_id] for path_id in suite.access_path_ids),
    )
    compiled = compile_suite(PACK / "suite.yaml", PACK / "cases.yaml", PROVIDERS)
    assert compiled.run_plan.cells[0].provider_id == "finnhub"


def test_ac4_stock_quote_outcomes_remain_categorical() -> None:
    rules = yaml.safe_load((PACK / "outcome-rules.yaml").read_text())

    assert rules["completion_requires"] == ["symbol", "price", "timestamp"]
    assert rules["negative_control_requires"] == ["validation_error"]


def test_ac5_stock_quote_requires_current_finite_price_or_an_error_fact() -> None:
    timestamp = datetime.now(UTC).isoformat()
    observation = extract_observation(
        PACK / "observation-schema.yaml",
        {"symbol": "AAPL", "price": 200.0, "timestamp": timestamp},
        "sha256:" + "a" * 64,
        "1.0.0",
    )
    outcome = evaluate_outcome(
        ("symbol", "price", "timestamp"), observation.facts, observation.evidence_ref
    )
    assert outcome.unmet_conditions == ()
    with pytest.raises(ExtractionError, match="stale"):
        extract_observation(
            PACK / "observation-schema.yaml",
            {
                "symbol": "AAPL",
                "price": 200.0,
                "timestamp": (datetime.now(UTC) - timedelta(minutes=16)).isoformat(),
            },
            "sha256:" + "a" * 64,
            "1.0.0",
        )
    with pytest.raises(ExtractionError, match="timezone"):
        extract_observation(
            PACK / "observation-schema.yaml",
            {"symbol": "AAPL", "price": 200.0, "timestamp": "2000-01-01T00:00:00"},
            "sha256:" + "a" * 64,
            "1.0.0",
        )
    with pytest.raises(ExtractionError, match="future"):
        extract_observation(
            PACK / "observation-schema.yaml",
            {
                "symbol": "AAPL",
                "price": 200.0,
                "timestamp": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
            },
            "sha256:" + "a" * 64,
            "1.0.0",
        )
    error = extract_observation(
        PACK / "observation-schema.yaml",
        {"validation_error": "unknown stock"},
        "sha256:" + "a" * 64,
        "1.0.0",
        negative_control=True,
    )
    assert error.facts == {"validation_error": "unknown stock"}
