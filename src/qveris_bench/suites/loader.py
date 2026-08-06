from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from qveris_bench.models.suite import BenchmarkCase, BenchmarkSuite


class SuiteLoadError(ValueError):
    pass


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SuiteLoadError(f"{path}: unable to load suite input: {exc}") from exc
    if not isinstance(loaded, dict):
        raise SuiteLoadError(f"{path}: YAML root must be a mapping")
    return loaded


def load_suite(path: Path) -> BenchmarkSuite:
    try:
        return BenchmarkSuite.model_validate(_load_yaml_mapping(path))
    except ValidationError as exc:
        raise SuiteLoadError(f"{path}: invalid suite: {exc}") from exc


def load_cases(path: Path) -> tuple[BenchmarkCase, ...]:
    data = _load_yaml_mapping(path)
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list):
        raise SuiteLoadError(f"{path}: cases must be a list")
    try:
        cases = tuple(BenchmarkCase.model_validate(item) for item in raw_cases)
    except ValidationError as exc:
        raise SuiteLoadError(f"{path}: invalid case: {exc}") from exc
    identities = [case.case_id for case in cases]
    duplicates = sorted(
        {case_id for case_id in identities if identities.count(case_id) > 1}
    )
    if duplicates:
        raise SuiteLoadError(f"{path}: duplicate cases: {', '.join(duplicates)}")
    return cases
