from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from qveris_bench.question_bank.models import QuestionSource
from qveris_bench.question_bank.repository import (
    QuestionBankValidationError,
    load_question_bank,
)

ROOT = Path(__file__).resolve().parents[2]


def test_ac1_question_bank_curates_ten_distinct_capabilities() -> None:
    bank = load_question_bank(ROOT / "question_bank")

    assert len(bank.capabilities) == 10
    assert {cap.cap_id for cap in bank.capabilities} == {
        "company-fundamentals",
        "corporate-actions",
        "economic-time-series",
        "etf-holdings",
        "financial-news-evidence",
        "financial-statement-facts",
        "historical-price-series",
        "index-constituents",
        "sec-filing-evidence",
        "stock-quote",
    }
    assert {cap.cap_id for cap in bank.capabilities if cap.lifecycle == "runnable"} == {
        "etf-holdings",
        "stock-quote",
    }


def test_ac2_every_question_has_one_cap_and_a_complete_evaluation_contract() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    known_capabilities = {cap.cap_id for cap in bank.capabilities}

    for question in bank.questions:
        assert question.cap_id in known_capabilities
        assert question.required_observations
        assert question.completion_conditions
        assert question.selection_rationale
        assert question.review_status == "approved"


def test_ac1_company_research_scenario_composes_three_p0_capabilities() -> None:
    bank = load_question_bank(ROOT / "question_bank")

    assert len(bank.scenarios) == 1
    scenario = bank.scenarios[0]
    assert (scenario.scenario_id, scenario.version) == (
        "company-research-agent",
        "1.0.0",
    )
    assert {requirement.cap_id for requirement in scenario.required_capabilities} == {
        "financial-statement-facts",
        "sec-filing-evidence",
        "stock-quote",
    }
    assert all(
        requirement.priority == "p0"
        for requirement in scenario.required_capabilities
    )


def test_ac2_every_capability_has_core_and_boundary_roles() -> None:
    bank = load_question_bank(ROOT / "question_bank")

    for capability in bank.capabilities:
        roles = {
            question.role
            for question in bank.questions
            if question.cap_id == capability.cap_id
        }
        assert {"core_positive", "boundary_negative"}.issubset(roles), (
            f"AC2 {capability.cap_id} must cover core and boundary roles"
        )


def test_ac2_question_bank_allows_multiple_questions_per_role(
    tmp_path: Path,
) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    questions_path = bank_root / "questions.yaml"
    document = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    duplicate = dict(document["questions"][0])
    duplicate["question_id"] = "etf-holdings-spy-weights-extra"
    document["questions"].append(duplicate)
    questions_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    bank = load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")

    assert len(bank.questions) == 21


def test_ac2_question_bank_rejects_missing_required_role(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    questions_path = bank_root / "questions.yaml"
    document = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    document["questions"] = [
        question
        for question in document["questions"]
        if question["question_id"] != "etf-holdings-invalid-symbol"
    ]
    questions_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="boundary_negative"):
        load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")


def test_ac3_migration_preserves_all_v1_question_ids() -> None:
    bank = load_question_bank(ROOT / "question_bank")

    expected = {
        "company-fundamentals-invalid-symbol",
        "company-fundamentals-msft-summary",
        "corporate-actions-aapl-split",
        "corporate-actions-invalid-action",
        "economic-time-series-invalid-series",
        "economic-time-series-unemployment",
        "etf-holdings-invalid-symbol",
        "etf-holdings-spy-weights",
        "financial-news-evidence-aapl-window",
        "financial-news-evidence-invalid-window",
        "financial-statement-facts-aapl-revenue",
        "financial-statement-facts-invalid-period",
        "historical-price-series-aapl-week",
        "historical-price-series-invalid-range",
        "index-constituents-invalid-index",
        "index-constituents-sp500",
        "sec-filing-evidence-aapl-risk",
        "sec-filing-evidence-invalid-filing-type",
        "stock-quote-aapl-current",
        "stock-quote-invalid-symbol",
    }
    assert {str(question.question_id) for question in bank.questions} == expected


def test_ac4_p0_questions_have_authoritative_evaluation_contracts() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    scenario = bank.scenarios[0]
    p0_cap_ids = {
        requirement.cap_id
        for requirement in scenario.required_capabilities
        if requirement.priority == "p0"
    }

    for question in bank.questions:
        if question.cap_id not in p0_cap_ids:
            continue
        assert scenario.scenario_id in question.scenario_ids
        assert question.evaluation_contract is not None
        assert question.evaluation_contract.reference_source_ids
        assert question.evaluation_contract.reference_rule
        assert question.evaluation_contract.tolerance_rule
        assert question.evaluation_contract.interface_expectations
        assert question.evaluation_contract.selection_implication


def test_ac1_scenario_rejects_unknown_capability(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    scenarios_path = bank_root / "scenarios.yaml"
    document = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    document["scenarios"][0]["required_capabilities"][0]["cap_id"] = "unknown-cap"
    scenarios_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="unknown capability"):
        load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")


def test_ac4_sources_are_citable_and_do_not_copy_external_task_text() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    source_ids = {source.source_id for source in bank.sources}

    assert all(source.reference_url for source in bank.sources)
    assert all(source.reproduction_policy == "citation_only" for source in bank.sources)
    assert {source.authority_tier for source in bank.sources} == {
        "official_api",
        "official_market_source",
        "external_benchmark",
    }
    assert all(
        set(question.source_ids).issubset(source_ids) for question in bank.questions
    )
    assert all(question.text_origin == "qveris_curated" for question in bank.questions)


def test_ac4_source_url_rejects_credentials_and_query_parameters() -> None:
    with pytest.raises(ValueError, match="canonical public HTTPS URL"):
        QuestionSource.model_validate(
            {
                "source_id": "unsafe-source",
                "name": "Unsafe source",
                "reference_url": "https://user:secret@example.com/data?token=secret",
                "authority_tier": "official_api",
                "reproduction_policy": "citation_only",
            }
        )


def test_ac5_question_validate_runs_through_the_installed_cli() -> None:
    executable = shutil.which("qveris-bench")
    assert executable is not None

    result = subprocess.run(
        [executable, "question", "validate"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "10 capabilities" in result.stdout
    assert "20 questions" in result.stdout
    assert result.stdout.endswith("1 scenario.\n")


def test_ac6_candidate_cannot_claim_an_executable_cap_pack(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    capabilities_path = bank_root / "capabilities.yaml"
    document = yaml.safe_load(capabilities_path.read_text(encoding="utf-8"))
    document["capabilities"][0]["lifecycle"] = "candidate"
    capabilities_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="candidate capability"):
        load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")


def test_ac6_runnable_requires_a_compilable_cap_pack(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    cap_packs_root = tmp_path / "cap_packs"
    shutil.copytree(ROOT / "cap_packs", cap_packs_root)
    (cap_packs_root / "etf_holdings" / "cap.yaml").write_text(
        "cap_id: etf-holdings\n", encoding="utf-8"
    )

    with pytest.raises(
        QuestionBankValidationError, match="invalid executable CAP pack"
    ):
        load_question_bank(bank_root, cap_packs_root=cap_packs_root)
