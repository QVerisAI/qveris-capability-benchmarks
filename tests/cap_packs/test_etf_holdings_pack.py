from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from qveris_bench.catalog.validation import validate_cap_file
from qveris_bench.outcomes.evaluator import evaluate_outcome
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation
from qveris_bench.suites.loader import load_cases, load_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs" / "etf_holdings"


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
    assert cases["invalid-etf"].negative_control
    assert cases["invalid-etf"].completion_conditions == ("validation_error",)


def test_ac3_etf_holdings_bindings_are_distinct_official_candidates() -> None:
    data = yaml.safe_load((PACK / "provider-bindings.yaml").read_text())
    bindings = data["access_paths"]

    assert 5 <= len(bindings) <= 8
    assert len({binding["provider_id"] for binding in bindings}) == len(bindings)
    assert len({binding["access_path_id"] for binding in bindings}) == len(bindings)
    assert all(
        binding["official_source"].startswith("https://") for binding in bindings
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
    error = extract_observation(
        PACK / "observation-schema.yaml",
        {"validation_error": "unknown ETF"},
        "sha256:" + "a" * 64,
        "1.0.0",
        negative_control=True,
    )
    assert error.facts == {"validation_error": "unknown ETF"}
