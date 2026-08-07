from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from qveris_bench.catalog.validation import CapValidationError, validate_cap_file
from qveris_bench.question_bank.models import (
    BankQuestion,
    CandidateCapability,
    DeveloperScenario,
    QuestionBank,
    QuestionSource,
)
from qveris_bench.suites.compiler import compile_suite
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping


class QuestionBankValidationError(ValueError):
    pass


def _load_records(path: Path, key: str) -> list[object]:
    try:
        document = load_yaml_mapping(path)
    except YamlDocumentError as exc:
        raise QuestionBankValidationError(f"{path}: invalid YAML: {exc}") from exc
    records = document.get(key)
    if not isinstance(records, list):
        raise QuestionBankValidationError(f"{path}: {key} must be a list")
    return records


def _validate_records[T](
    records: list[object], model: type[T], label: str
) -> tuple[T, ...]:
    try:
        return tuple(model.model_validate(record) for record in records)  # type: ignore[attr-defined]
    except ValidationError as exc:
        raise QuestionBankValidationError(f"invalid {label}: {exc}") from exc


def _require_unique(values: tuple[object, ...], attribute: str, label: str) -> None:
    ids = [str(getattr(value, attribute)) for value in values]
    if len(ids) != len(set(ids)):
        raise QuestionBankValidationError(f"duplicate {label}")


def _cap_packs_by_id(cap_packs_root: Path) -> dict[str, tuple[Path, ...]]:
    packs: dict[str, list[Path]] = {}
    for path in sorted(cap_packs_root.glob("*/cap.yaml")):
        if path.parent.name.startswith("_"):
            continue
        try:
            cap = validate_cap_file(path)
        except CapValidationError as exc:
            raise QuestionBankValidationError(
                f"{path}: invalid executable CAP pack: {exc}"
            ) from exc
        packs.setdefault(str(cap.cap_id), []).append(path)
    return {cap_id: tuple(paths) for cap_id, paths in packs.items()}


def _require_compilable_cap_pack(
    cap_id: str, cap_paths: tuple[Path, ...], providers_root: Path
) -> None:
    for cap_path in cap_paths:
        try:
            compile_suite(
                suite_path=cap_path.with_name("suite.yaml"),
                cases_path=cap_path.with_name("cases.yaml"),
                providers_root=providers_root,
                cap_path=cap_path,
            )
        except (OSError, ValueError):
            continue
        return
    raise QuestionBankValidationError(
        f"runnable capability {cap_id} has no compilable executable CAP pack"
    )


def _validate_cross_references(
    sources: tuple[QuestionSource, ...],
    capabilities: tuple[CandidateCapability, ...],
    questions: tuple[BankQuestion, ...],
    scenarios: tuple[DeveloperScenario, ...],
    cap_packs_root: Path,
) -> None:
    _require_unique(sources, "source_id", "source IDs")
    _require_unique(capabilities, "cap_id", "capability IDs")
    _require_unique(questions, "question_id", "question IDs")
    _require_unique(scenarios, "scenario_id", "scenario IDs")
    source_ids = {str(source.source_id) for source in sources}
    capability_ids = {str(capability.cap_id) for capability in capabilities}
    scenario_ids = {str(scenario.scenario_id) for scenario in scenarios}
    for question in questions:
        if str(question.cap_id) not in capability_ids:
            raise QuestionBankValidationError(
                "question references an unknown capability"
            )
        if not set(map(str, question.source_ids)).issubset(source_ids):
            raise QuestionBankValidationError("question references an unknown source")
        if not set(map(str, question.scenario_ids)).issubset(scenario_ids):
            raise QuestionBankValidationError("question references an unknown scenario")
        if question.evaluation_contract is not None and not set(
            map(str, question.evaluation_contract.reference_source_ids)
        ).issubset(set(map(str, question.source_ids))):
            raise QuestionBankValidationError(
                "evaluation contract references a source not cited by the question"
            )
    for capability in capabilities:
        roles = {
            str(question.role)
            for question in questions
            if question.cap_id == capability.cap_id
        }
        missing_roles = {"core_positive", "boundary_negative"} - roles
        if missing_roles:
            raise QuestionBankValidationError(
                f"capability {capability.cap_id} requires question roles: "
                + ", ".join(sorted(missing_roles))
            )
    p0_capability_ids: set[str] = set()
    for scenario in scenarios:
        if not set(map(str, scenario.source_ids)).issubset(source_ids):
            raise QuestionBankValidationError("scenario references an unknown source")
        for requirement in scenario.required_capabilities:
            cap_id = str(requirement.cap_id)
            if cap_id not in capability_ids:
                raise QuestionBankValidationError(
                    f"scenario references unknown capability: {cap_id}"
                )
            roles = {
                str(question.role)
                for question in questions
                if question.cap_id == requirement.cap_id
            }
            missing_roles = set(map(str, requirement.minimum_question_roles)) - roles
            if missing_roles:
                raise QuestionBankValidationError(
                    f"scenario {scenario.scenario_id} lacks question roles for "
                    f"{cap_id}: {', '.join(sorted(missing_roles))}"
                )
            if requirement.priority == "p0":
                p0_capability_ids.add(cap_id)
    for question in questions:
        if str(question.cap_id) not in p0_capability_ids:
            continue
        if not question.scenario_ids:
            raise QuestionBankValidationError(
                "P0 question requires a scenario reference"
            )
        if question.evaluation_contract is None:
            raise QuestionBankValidationError(
                "P0 question requires an authoritative evaluation contract"
            )
    cap_packs_by_id = _cap_packs_by_id(cap_packs_root)
    providers_root = cap_packs_root.parent / "providers"
    for capability in capabilities:
        cap_id = str(capability.cap_id)
        cap_paths = cap_packs_by_id.get(cap_id, ())
        is_pack = bool(cap_paths)
        if capability.lifecycle == "runnable" and not is_pack:
            raise QuestionBankValidationError(
                f"runnable capability {capability.cap_id} has no executable cap pack"
            )
        if capability.lifecycle == "runnable":
            _require_compilable_cap_pack(cap_id, cap_paths, providers_root)
        if capability.lifecycle == "candidate" and is_pack:
            raise QuestionBankValidationError(
                f"candidate capability {capability.cap_id} already has an executable "
                "cap pack"
            )


def load_question_bank(root: Path, cap_packs_root: Path | None = None) -> QuestionBank:
    sources = _validate_records(
        _load_records(root / "sources.yaml", "sources"), QuestionSource, "sources"
    )
    capabilities = _validate_records(
        _load_records(root / "capabilities.yaml", "capabilities"),
        CandidateCapability,
        "capabilities",
    )
    questions = _validate_records(
        _load_records(root / "questions.yaml", "questions"), BankQuestion, "questions"
    )
    scenarios = _validate_records(
        _load_records(root / "scenarios.yaml", "scenarios"),
        DeveloperScenario,
        "scenarios",
    )
    _validate_cross_references(
        sources,
        capabilities,
        questions,
        scenarios,
        cap_packs_root or root.parent / "cap_packs",
    )
    return QuestionBank(
        sources=sources,
        capabilities=capabilities,
        questions=questions,
        scenarios=scenarios,
    )
