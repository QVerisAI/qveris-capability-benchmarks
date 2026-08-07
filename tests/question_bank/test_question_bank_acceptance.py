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


def test_ac3_every_capability_has_a_positive_and_negative_question() -> None:
    bank = load_question_bank(ROOT / "question_bank")

    for capability in bank.capabilities:
        counts = {
            variant: sum(
                question.cap_id == capability.cap_id and question.variant == variant
                for question in bank.questions
            )
            for variant in ("positive", "negative")
        }
        assert counts == {"positive": 1, "negative": 1}


def test_ac3_question_bank_rejects_duplicate_variant_coverage(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    questions_path = bank_root / "questions.yaml"
    document = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    duplicate = dict(document["questions"][0])
    duplicate["question_id"] = "etf-holdings-spy-weights-extra"
    document["questions"].append(duplicate)
    questions_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="exactly one"):
        load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")


def test_ac4_sources_are_citable_and_do_not_copy_external_task_text() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    source_ids = {source.source_id for source in bank.sources}

    assert all(source.reference_url for source in bank.sources)
    assert all(source.reproduction_policy == "citation_only" for source in bank.sources)
    assert {source.authority_tier for source in bank.sources} == {
        "official_api",
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


def test_ac6_candidate_cannot_claim_an_executable_cap_pack(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    bank_root.mkdir()
    (bank_root / "sources.yaml").write_text(
        "sources:\n"
        "  - source_id: qveris\n"
        "    name: QVeris curated source\n"
        "    reference_url: https://example.com/source\n"
        "    authority_tier: official_api\n"
        "    reproduction_policy: citation_only\n",
        encoding="utf-8",
    )
    (bank_root / "capabilities.yaml").write_text(
        "capabilities:\n"
        "  - cap_id: etf-holdings\n"
        "    name: ETF Holdings\n"
        "    lifecycle: candidate\n"
        "    business_use: Select a provider for ETF holdings data.\n",
        encoding="utf-8",
    )
    (bank_root / "questions.yaml").write_text(
        "questions:\n"
        "  - question_id: etf-holdings-positive\n"
        "    cap_id: etf-holdings\n"
        "    variant: positive\n"
        "    task: Return ETF holdings.\n"
        "    input: {symbol: SPY}\n"
        "    required_observations: [symbol]\n"
        "    completion_conditions: [symbol]\n"
        "    source_ids: [qveris]\n"
        "    text_origin: qveris_curated\n"
        "    selection_rationale: Maps directly to the ETF holdings capability.\n"
        "    review_status: approved\n"
        "  - question_id: etf-holdings-negative\n"
        "    cap_id: etf-holdings\n"
        "    variant: negative\n"
        "    task: Reject an invalid ETF symbol.\n"
        "    input: {symbol: NOTANETF}\n"
        "    required_observations: [validation_error]\n"
        "    completion_conditions: [validation_error]\n"
        "    source_ids: [qveris]\n"
        "    text_origin: qveris_curated\n"
        "    selection_rationale: Verifies safe rejection for the same capability.\n"
        "    review_status: approved\n",
        encoding="utf-8",
    )

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
