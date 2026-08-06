from __future__ import annotations

from pathlib import Path

from pydantic import Field, ValidationError

from qveris_bench.models.base import FrozenModel
from qveris_bench.models.suite import BenchmarkCase, BenchmarkSuite
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping


class SuiteLoadError(ValueError):
    pass


class CasesDocument(FrozenModel):
    cases: tuple[BenchmarkCase, ...] = Field(min_length=1)


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    try:
        return load_yaml_mapping(path)
    except YamlDocumentError as exc:
        raise SuiteLoadError(f"{path}: unable to load suite input: {exc}") from exc


def load_suite(path: Path) -> BenchmarkSuite:
    try:
        return BenchmarkSuite.model_validate(_load_yaml_mapping(path))
    except ValidationError as exc:
        raise SuiteLoadError(f"{path}: invalid suite: {exc}") from exc


def load_cases(path: Path) -> tuple[BenchmarkCase, ...]:
    try:
        cases = CasesDocument.model_validate(_load_yaml_mapping(path)).cases
    except ValidationError as exc:
        raise SuiteLoadError(f"{path}: invalid case: {exc}") from exc
    identities = [case.case_id for case in cases]
    duplicates = sorted(
        {case_id for case_id in identities if identities.count(case_id) > 1}
    )
    if duplicates:
        raise SuiteLoadError(f"{path}: duplicate cases: {', '.join(duplicates)}")
    return cases
