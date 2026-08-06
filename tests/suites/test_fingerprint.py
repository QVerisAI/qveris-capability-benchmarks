from __future__ import annotations

from pathlib import Path

import yaml

from qveris_bench.suites.compiler import compile_suite

from .test_suite_compiler_acceptance import _provider_data, _write_inputs


def test_ac6_fingerprint_is_stable_for_equivalent_yaml(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    first = compile_suite(suite_path, cases_path, providers_root)
    suite_data = yaml.safe_load(suite_path.read_text())
    suite_path.write_text(yaml.safe_dump(suite_data, sort_keys=True))

    second = compile_suite(suite_path, cases_path, providers_root)

    assert first.fingerprint == second.fingerprint, (
        "AC6 YAML key order must not change the fingerprint"
    )


def test_ac6_fingerprint_changes_when_frozen_input_changes(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    first = compile_suite(suite_path, cases_path, providers_root)
    suite_data = yaml.safe_load(suite_path.read_text())
    suite_data["rounds"] = 3
    suite_path.write_text(yaml.safe_dump(suite_data, sort_keys=False))

    second = compile_suite(suite_path, cases_path, providers_root)

    assert first.fingerprint != second.fingerprint, (
        "AC6 a frozen field change must create a new fingerprint"
    )


def test_ac6_fingerprint_covers_excluded_candidate_cohort(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    first = compile_suite(suite_path, cases_path, providers_root)
    excluded = _provider_data(
        "excluded-provider",
        "excluded-official-api",
        "official_api",
        False,
        "c",
    )
    excluded["qualification"]["disposition"] = "excluded"
    excluded_path = providers_root / "excluded" / "provider.yaml"
    excluded_path.parent.mkdir(parents=True)
    excluded_path.write_text(yaml.safe_dump(excluded, sort_keys=False))

    second = compile_suite(suite_path, cases_path, providers_root)

    assert first.fingerprint != second.fingerprint, (
        "AC6 terminal excluded candidates are part of the frozen cohort"
    )
