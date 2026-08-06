from __future__ import annotations

from pathlib import Path

from pydantic import Field, ValidationError

from qveris_bench.models.base import FrozenModel
from qveris_bench.models.suite import BenchmarkCase
from qveris_bench.yaml_io import load_yaml_mapping


class OutcomeRulesError(ValueError):
    pass


class OutcomeRules(FrozenModel):
    completion_requires: tuple[str, ...] = Field(min_length=1)
    negative_control_requires: tuple[str, ...] = Field(min_length=1)


def load_outcome_rules(path: Path) -> OutcomeRules:
    try:
        return OutcomeRules.model_validate(load_yaml_mapping(path))
    except (OSError, ValidationError, ValueError) as exc:
        raise OutcomeRulesError(f"invalid outcome rules: {path}") from exc


def validate_outcome_rules(
    rules: OutcomeRules, cases: tuple[BenchmarkCase, ...]
) -> None:
    for case in cases:
        expected = (
            rules.negative_control_requires
            if case.negative_control
            else rules.completion_requires
        )
        if case.completion_conditions != expected:
            raise OutcomeRulesError(
                f"case conditions do not match outcome rules: {case.case_id}"
            )
