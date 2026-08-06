from qveris_bench.models.enums import OutcomeStatus
from qveris_bench.outcomes.evaluator import evaluate_outcome


def test_ac2_outcomes_are_categorical_and_report_unmet_conditions() -> None:
    outcome = evaluate_outcome(
        ("symbol", "price"), {"symbol": "AAPL"}, "sha256:" + "a" * 64
    )

    assert outcome.status is OutcomeStatus.PARTIAL
    assert outcome.unmet_conditions == ("price",)
    assert outcome.evidence_refs
