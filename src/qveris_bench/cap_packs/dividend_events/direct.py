from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qveris_bench.cap_packs.dividend_events.extractors import (
    DividendExtractionError,
    DividendNegativeControlError,
    extract_dividend_event,
)
from qveris_bench.models.enums import CellState, FailureAttribution, OutcomeStatus
from qveris_bench.models.run import RequestIdentity
from qveris_bench.models.suite import BenchmarkCase
from qveris_bench.outcomes.evaluator import evaluate_outcome
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation


class DividendDirectError(ValueError):
    pass


@dataclass(frozen=True)
class DividendDirectResult:
    state: CellState
    facts: dict[str, Any]
    unmet_conditions: tuple[str, ...]
    failure_attribution: FailureAttribution | None


def evaluate_dividend_document(
    provider_id: str,
    document: object,
    case: BenchmarkCase,
    schema_path: Path,
    evidence_ref: str,
    *,
    request_identity: RequestIdentity | None = None,
) -> DividendDirectResult:
    try:
        facts = extract_dividend_event(
            provider_id,
            document,
            symbol=str(case.input["symbol"]),
            start_date=_optional_string(case.input.get("start_date")),
            end_date=_optional_string(case.input.get("end_date")),
            negative_control=case.negative_control,
            request_identity=request_identity,
        )
    except DividendNegativeControlError:
        return DividendDirectResult(
            state=CellState.PROVIDER_NEGATIVE,
            facts={},
            unmet_conditions=("validation_error",),
            failure_attribution=FailureAttribution.PROVIDER_VALIDATION_ERROR,
        )
    except DividendExtractionError as exc:
        raise DividendDirectError("could not extract dividend response") from exc

    try:
        observation = extract_observation(
            schema_path,
            facts,
            evidence_ref,
            "1.0.0",
            negative_control=case.negative_control,
        )
    except ExtractionError as exc:
        raise DividendDirectError("dividend observation contract failed") from exc
    outcome = evaluate_outcome(
        case.completion_conditions, observation.facts, evidence_ref
    )
    if (
        request_identity is not None
        and observation.facts.get("identity_verified") is not True
    ):
        unmet = tuple(dict.fromkeys((*outcome.unmet_conditions, "identity_verified")))
        return DividendDirectResult(
            CellState.PROVIDER_NEGATIVE,
            facts,
            unmet,
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    if outcome.status is OutcomeStatus.COMPLETED:
        return DividendDirectResult(CellState.COMPLETED, facts, (), None)
    return DividendDirectResult(
        CellState.PROVIDER_NEGATIVE,
        facts,
        outcome.unmet_conditions,
        FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    )


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None
