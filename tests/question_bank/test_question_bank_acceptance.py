from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from qveris_bench.question_bank.repository import (
    QuestionBankValidationError,
    load_question_bank,
)

ROOT = Path(__file__).resolve().parents[2]


def test_ac1_question_bank_contains_only_harbor_candidates() -> None:
    bank = load_question_bank(ROOT / "question_bank")

    assert {str(cap.cap_id) for cap in bank.capabilities} == {
        "corporate-actions",
        "crypto-spot-quote",
        "dividend-events",
        "financial-ratios",
        "fx-spot-rate",
        "govt-bond-yield",
        "realtime-financial-news",
    }, "AC1 candidates must come from the Harbor-selected CAP set"
    lifecycle_by_cap = {
        str(cap.cap_id): str(cap.lifecycle) for cap in bank.capabilities
    }
    assert lifecycle_by_cap == {
        "corporate-actions": "runnable",
        "crypto-spot-quote": "runnable",
        "dividend-events": "runnable",
        "financial-ratios": "candidate",
        "fx-spot-rate": "candidate",
        "govt-bond-yield": "candidate",
        "realtime-financial-news": "candidate",
    }, "AC1 runnable CAPs must have a formal Harbor-backed pack"
    assert {str(cap.source_id) for cap in bank.capabilities} == {
        "harbor-capability-catalog"
    }


def test_ac2_every_candidate_has_contract_derived_core_and_boundary_questions() -> None:
    bank = load_question_bank(ROOT / "question_bank")

    for capability in bank.capabilities:
        questions = [
            question
            for question in bank.questions
            if question.cap_id == capability.cap_id
        ]
        assert {"core_positive", "boundary_negative"}.issubset(
            {question.role for question in questions}
        ), f"AC2 {capability.cap_id} must retain the minimum CAP question pair"
        source_ids = {
            str(source_id)
            for question in questions
            for source_id in question.source_ids
        }
        assert source_ids == {"harbor-capability-catalog"}


def test_ac3_question_bank_rejects_non_harbor_candidate_source(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "harbor_catalog", tmp_path / "harbor_catalog")
    shutil.copytree(ROOT / "question_bank", bank_root)
    capabilities_path = bank_root / "capabilities.yaml"
    document = yaml.safe_load(capabilities_path.read_text(encoding="utf-8"))
    document["capabilities"][0]["source_id"] = "external-benchmark"
    capabilities_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="source_id"):
        load_question_bank(bank_root)


def test_ac3_question_bank_rejects_a_candidate_missing_from_public_contracts(
    tmp_path: Path,
) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    shutil.copytree(ROOT / "harbor_catalog", tmp_path / "harbor_catalog")
    capabilities_path = bank_root / "capabilities.yaml"
    document = yaml.safe_load(capabilities_path.read_text(encoding="utf-8"))
    document["capabilities"][0]["harbor_capability_id"] = "MKT.NOT_EXPORTED"
    capabilities_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="public Harbor contracts"):
        load_question_bank(bank_root)


def test_ac3_question_bank_rejects_an_orphan_executable_cap_pack(
    tmp_path: Path,
) -> None:
    bank_root = tmp_path / "question_bank"
    packs_root = tmp_path / "cap_packs"
    shutil.copytree(ROOT / "question_bank", bank_root)
    shutil.copytree(ROOT / "harbor_catalog", tmp_path / "harbor_catalog")
    orphan = packs_root / "orphan" / "cap.yaml"
    orphan.parent.mkdir(parents=True)
    orphan.write_text(
        yaml.safe_dump(
            {
                "cap_id": "orphan-cap",
                "version": "1.0.0",
                "name": "Orphan CAP",
                "business_use": "This CAP must be declared in the candidate catalog.",
                "scope": ["Test scope"],
                "sources": [
                    {
                        "source_type": "harbor_catalog",
                        "harbor_capability_id": "MKT.ORPHAN",
                        "contract_version": 1,
                        "catalog_snapshot_digest": "a" * 64,
                        "contract_digest": "b" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(QuestionBankValidationError, match="missing from the Harbor"):
        load_question_bank(bank_root, packs_root)


def test_ac4_question_validate_runs_through_the_installed_cli() -> None:
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
    assert "7 capabilities" in result.stdout
    assert "16 questions" in result.stdout
    assert result.stdout.endswith("16 questions.\n")
