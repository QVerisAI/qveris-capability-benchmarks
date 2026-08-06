from pathlib import Path

import pytest

from qveris_bench.outcomes.extractor import ExtractionError, extract_observation


def test_ac1_observation_is_bound_to_evidence_and_cap_schema(tmp_path: Path) -> None:
    schema = tmp_path / "observation-schema.yaml"
    schema.write_text("required_fields: [symbol, price]\n")

    observation = extract_observation(
        schema,
        {"symbol": "AAPL", "price": 10},
        "sha256:" + "a" * 64,
        "1.0.0",
    )

    assert observation.evidence_ref.startswith("sha256:")
    assert observation.facts["symbol"] == "AAPL"


def test_ac1_extractor_rejects_missing_cap_owned_field(tmp_path: Path) -> None:
    schema = tmp_path / "observation-schema.yaml"
    schema.write_text("required_fields: [symbol, price]\n")
    with pytest.raises(ExtractionError, match="price"):
        extract_observation(schema, {"symbol": "AAPL"}, "sha256:" + "a" * 64, "1.0.0")
