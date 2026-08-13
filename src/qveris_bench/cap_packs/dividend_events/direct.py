from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qveris_bench.cap_packs.dividend_events.extractors import (
    DividendExtractionError,
    DividendNegativeControlError,
    extract_dividend_event,
)
from qveris_bench.cap_packs.dividend_events.models import DividendRequestIdentity
from qveris_bench.execution.direct_binding import DirectBinding
from qveris_bench.models.enums import CellState, FailureAttribution, OutcomeStatus
from qveris_bench.models.suite import BenchmarkCase
from qveris_bench.outcomes.evaluator import evaluate_outcome
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation
from qveris_bench.releases.public_terminal import ValidatedTerminalOutcome


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
    request_identity: DividendRequestIdentity | None = None,
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


def validate_public_dividend_outcome(
    case: BenchmarkCase,
    binding: DirectBinding,
    facts: dict[str, Any],
    schema_path: Path,
) -> ValidatedTerminalOutcome:
    try:
        observation = extract_observation(
            schema_path,
            facts,
            "sha256:" + "0" * 64,
            "1.0.0",
            negative_control=case.negative_control,
        )
    except ExtractionError as exc:
        raise DividendDirectError("public dividend facts failed schema") from exc
    outcome = evaluate_outcome(
        case.completion_conditions, observation.facts, "sha256:" + "0" * 64
    )
    unmet = outcome.unmet_conditions
    if not case.negative_control:
        identity = DividendRequestIdentity.model_validate(binding.request_identity)
        basis = observation.facts.get("identity_basis")
        returned = observation.facts.get("returned_symbol")
        identity_valid = (
            observation.facts.get("symbol") == case.input.get("symbol")
            and identity.canonical_symbol == case.input.get("symbol")
            and (
                (basis == "request_bound" and returned is None)
                or (
                    basis == "response_field"
                    and isinstance(returned, str)
                    and _symbol_base(returned)
                    in {
                        _symbol_base(identity.vendor_symbol),
                        _symbol_base(identity.canonical_symbol),
                    }
                )
            )
        )
        if not identity_valid:
            unmet = tuple(dict.fromkeys((*unmet, "identity_verified")))
    if unmet:
        return ValidatedTerminalOutcome(
            CellState.PROVIDER_NEGATIVE,
            unmet,
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    return ValidatedTerminalOutcome(CellState.COMPLETED, (), None)


def _symbol_base(value: str) -> str:
    return value.strip().upper().split(":", 1)[0].split(".", 1)[0]
