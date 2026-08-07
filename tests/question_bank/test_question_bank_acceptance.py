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
        "financial-statement-facts",
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

    assert len(bank.scenarios) == 2
    scenario = next(
        scenario for scenario in bank.scenarios if str(scenario.version) == "1.0.0"
    )
    assert (scenario.scenario_id, scenario.version) == (
        "company-research-agent",
        "1.0.0",
    )
    assert scenario.markets == ("united-states",)
    assert scenario.languages == ("english",)
    assert {requirement.cap_id for requirement in scenario.required_capabilities} == {
        "company-fundamentals",
        "financial-statement-facts",
        "financial-news-evidence",
        "historical-price-series",
        "sec-filing-evidence",
        "stock-quote",
    }
    assert {
        requirement.cap_id
        for requirement in scenario.required_capabilities
        if requirement.priority == "p0"
    } == {"financial-statement-facts", "sec-filing-evidence", "stock-quote"}
    assert scenario.completion_policy.required_priorities == ("p0",)
    assert scenario.completion_policy.missing_dimension_state == (
        "evidence_insufficient"
    )
    expanded = next(
        scenario for scenario in bank.scenarios if str(scenario.version) == "1.1.0"
    )
    assert expanded.markets == ("united-states", "mainland-china")
    assert expanded.languages == ("english", "simplified-chinese")
    assert {requirement.cap_id for requirement in expanded.required_capabilities} == {
        requirement.cap_id for requirement in scenario.required_capabilities
    }


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

    assert len(bank.questions) == len(document["questions"])


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
    assert expected.issubset({str(question.question_id) for question in bank.questions})


def test_ac_sq1_stock_quote_question_family_covers_selection_roles() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    questions = [
        question for question in bank.questions if question.cap_id == "stock-quote"
    ]

    assert {str(question.question_id) for question in questions} == {
        "stock-quote-600519-agent-contract",
        "stock-quote-600519-market-coverage",
        "stock-quote-aapl-current",
        "stock-quote-aapl-freshness-precision",
        "stock-quote-invalid-symbol",
    }
    assert {question.role for question in questions} == {
        "agent_contract",
        "boundary_negative",
        "core_positive",
        "coverage",
        "freshness_precision",
    }


def test_ac_sq2_stock_quote_family_has_scenario_and_evaluation_contracts() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    scenario = next(
        scenario for scenario in bank.scenarios if str(scenario.version) == "1.1.0"
    )
    stock_requirement = next(
        requirement
        for requirement in scenario.required_capabilities
        if requirement.cap_id == "stock-quote"
    )

    assert set(stock_requirement.minimum_question_roles) == {
        "agent_contract",
        "boundary_negative",
        "core_positive",
        "coverage",
        "freshness_precision",
    }
    for question in bank.questions:
        if question.cap_id != "stock-quote":
            continue
        assert any(
            reference.scenario_id == scenario.scenario_id
            and reference.version == scenario.version
            for reference in question.scenario_refs
        )
        assert question.evaluation_contract is not None
        assert question.evaluation_contract.reference_source_ids
        assert question.evaluation_contract.tolerance_rule
        assert question.evaluation_contract.selection_implication


def test_ac_sq4_agent_contract_question_is_provider_neutral() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    question = next(
        question
        for question in bank.questions
        if question.question_id == "stock-quote-600519-agent-contract"
    )

    serialized = question.model_dump_json(
        include={
            "task",
            "input",
            "required_observations",
            "completion_conditions",
            "source_ids",
            "evaluation_contract",
            "selection_rationale",
        }
    ).lower()
    assert question.input == {
        "symbol": "600519.SH",
        "market": "CN",
        "fields": ["price", "quote_time"],
    }
    assert "获取贵州茅台当前价格和报价时间" in question.task
    assert all(
        provider not in serialized
        for provider in ("wind", "finnhub", "eodhd", "qveris")
    )
    sources_by_id = {str(source.source_id): source for source in bank.sources}
    references = {
        sources_by_id[str(source_id)]
        for source_id in question.evaluation_contract.reference_source_ids
    }
    assert {source.authority_tier for source in references} == {
        "official_market_source"
    }
    assert all(
        (source.reference_url.host or "").removesuffix(".").endswith("sse.com.cn")
        for source in references
    )
    assert (
        "cap-owned canonical identity"
        in question.evaluation_contract.reference_rule.lower()
    )
    assert "xshg" in question.evaluation_contract.reference_rule.lower()


def test_ac_sq3_market_coverage_is_scoped_to_sse_single_security() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    question = next(
        question
        for question in bank.questions
        if question.question_id == "stock-quote-600519-market-coverage"
    )
    sources_by_id = {str(source.source_id): source for source in bank.sources}
    references = {
        sources_by_id[str(source_id)]
        for source_id in question.evaluation_contract.reference_source_ids
    }
    assert {source.authority_tier for source in references} == {
        "official_market_source"
    }
    assert (
        "single-security" in question.evaluation_contract.selection_implication.lower()
    )
    assert (
        "cap-owned canonical identity"
        in question.evaluation_contract.reference_rule.lower()
    )
    assert "xshg" in question.evaluation_contract.reference_rule.lower()


def test_ac_sq5_freshness_contract_has_executable_tolerances() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    question = next(
        question
        for question in bank.questions
        if question.question_id == "stock-quote-aapl-freshness-precision"
    )
    tolerance = question.evaluation_contract.tolerance_rule.lower()
    assert "15 minutes" in tolerance
    assert "latest disclosed close" in tolerance
    assert (
        "capture the reference price"
        in question.evaluation_contract.reference_rule.lower()
    )


def test_ac4_p0_questions_have_authoritative_evaluation_contracts() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    for scenario in bank.scenarios:
        p0_cap_ids = {
            requirement.cap_id
            for requirement in scenario.required_capabilities
            if requirement.priority == "p0"
        }
        for question in bank.questions:
            if question.cap_id not in p0_cap_ids:
                continue
            if not any(
                reference.scenario_id == scenario.scenario_id
                and reference.version == scenario.version
                for reference in question.scenario_refs
            ):
                continue
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


def test_ac1_scenario_roles_ignore_questions_linked_to_another_scenario(
    tmp_path: Path,
) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    scenarios_path = bank_root / "scenarios.yaml"
    scenarios = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    other = dict(scenarios["scenarios"][0])
    other["scenario_id"] = "portfolio-monitoring-agent"
    scenarios["scenarios"].append(other)
    scenarios_path.write_text(yaml.safe_dump(scenarios), encoding="utf-8")
    questions_path = bank_root / "questions.yaml"
    questions = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    for question in questions["questions"]:
        if question["question_id"] == "stock-quote-aapl-current":
            question["scenario_refs"] = [
                {"scenario_id": "portfolio-monitoring-agent", "version": "1.0.0"}
            ]
    questions_path.write_text(yaml.safe_dump(questions), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="company-research-agent"):
        load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")


def test_ac1_scenario_rejects_question_for_unrequired_capability(
    tmp_path: Path,
) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    questions_path = bank_root / "questions.yaml"
    questions = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    questions["questions"][0]["scenario_refs"] = [
        {"scenario_id": "company-research-agent", "version": "1.0.0"}
    ]
    questions_path.write_text(yaml.safe_dump(questions), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="not required"):
        load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")


def test_ac1_scenario_rejects_duplicate_capability_requirements(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    scenarios_path = bank_root / "scenarios.yaml"
    document = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    duplicate = dict(document["scenarios"][0]["required_capabilities"][0])
    duplicate["priority"] = "p1"
    document["scenarios"][0]["required_capabilities"].append(duplicate)
    scenarios_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="duplicate capability"):
        load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")


def test_ac1_completion_policy_controls_required_evaluation_contracts(
    tmp_path: Path,
) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    scenarios_path = bank_root / "scenarios.yaml"
    document = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    document["scenarios"][0]["completion_policy"]["required_priorities"] = [
        "p0",
        "p1",
    ]
    scenarios_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="required scenario question"):
        load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")


def test_ac1_scenario_identity_includes_semantic_version(tmp_path: Path) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    scenarios_path = bank_root / "scenarios.yaml"
    scenarios = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    next_version = dict(scenarios["scenarios"][0])
    next_version["version"] = "1.2.0"
    scenarios["scenarios"].append(next_version)
    scenarios_path.write_text(yaml.safe_dump(scenarios), encoding="utf-8")
    questions_path = bank_root / "questions.yaml"
    questions = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    for question in questions["questions"]:
        if question.get("scenario_refs"):
            question["scenario_refs"].append(
                {"scenario_id": "company-research-agent", "version": "1.2.0"}
            )
    questions_path.write_text(yaml.safe_dump(questions), encoding="utf-8")

    bank = load_question_bank(bank_root, cap_packs_root=ROOT / "cap_packs")

    assert {
        (scenario.scenario_id, scenario.version) for scenario in bank.scenarios
    } == {
        ("company-research-agent", "1.0.0"),
        ("company-research-agent", "1.1.0"),
        ("company-research-agent", "1.2.0"),
    }


def test_ac4_p0_contract_rejects_external_benchmark_as_only_reference(
    tmp_path: Path,
) -> None:
    bank_root = tmp_path / "question_bank"
    shutil.copytree(ROOT / "question_bank", bank_root)
    questions_path = bank_root / "questions.yaml"
    questions = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    questions["questions"][2]["evaluation_contract"]["reference_source_ids"] = [
        "finsearchcomp-2026"
    ]
    questions_path.write_text(yaml.safe_dump(questions), encoding="utf-8")

    with pytest.raises(QuestionBankValidationError, match="authoritative source"):
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
    for source in bank.sources:
        if source.authority_tier != "external_benchmark":
            continue
        if source.reference_url.host == "github.com":
            assert source.repository_commit
            assert source.source_task_ids


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


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/internal",
        "https://[::1]/internal",
        "https://localhost./internal",
        "https://source.internal./internal",
    ],
)
def test_ac4_source_url_rejects_private_network_hosts(url: str) -> None:
    with pytest.raises(ValueError, match="public host"):
        QuestionSource.model_validate(
            {
                "source_id": "private-source",
                "name": "Private source",
                "reference_url": url,
                "authority_tier": "official_api",
                "reproduction_policy": "citation_only",
            }
        )


def test_ac4_external_repository_requires_immutable_provenance() -> None:
    with pytest.raises(ValueError, match="immutable repository provenance"):
        QuestionSource.model_validate(
            {
                "source_id": "mutable-benchmark",
                "name": "Mutable benchmark",
                "reference_url": "https://github.com/example/benchmark",
                "authority_tier": "external_benchmark",
                "reproduction_policy": "citation_only",
            }
        )


@pytest.mark.parametrize(
    ("url", "commit", "task_ids"),
    [
        ("https://github.com./example/benchmark", None, ()),
        ("https://github.com/example/benchmark", "a" * 40, ("",)),
    ],
)
def test_ac4_external_repository_rejects_provenance_bypasses(
    url: str,
    commit: str | None,
    task_ids: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="immutable repository provenance"):
        QuestionSource.model_validate(
            {
                "source_id": "mutable-benchmark",
                "name": "Mutable benchmark",
                "reference_url": url,
                "authority_tier": "external_benchmark",
                "reproduction_policy": "citation_only",
                "repository_commit": commit,
                "source_task_ids": task_ids,
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
    assert "23 questions" in result.stdout
    assert result.stdout.endswith("2 scenarios.\n")


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
