from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from qveris_bench.question_bank.models import (
    BankQuestion,
    CandidateCapability,
    QuestionBank,
    QuestionSource,
)
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


def _cap_pack_ids(cap_packs_root: Path) -> set[str]:
    ids: set[str] = set()
    for path in cap_packs_root.glob("*/cap.yaml"):
        try:
            document = load_yaml_mapping(path)
        except YamlDocumentError as exc:
            raise QuestionBankValidationError(
                f"{path}: invalid CAP YAML: {exc}"
            ) from exc
        cap_id = document.get("cap_id")
        if isinstance(cap_id, str):
            ids.add(cap_id)
    return ids


def _validate_cross_references(
    sources: tuple[QuestionSource, ...],
    capabilities: tuple[CandidateCapability, ...],
    questions: tuple[BankQuestion, ...],
    cap_packs_root: Path,
) -> None:
    _require_unique(sources, "source_id", "source IDs")
    _require_unique(capabilities, "cap_id", "capability IDs")
    _require_unique(questions, "question_id", "question IDs")
    source_ids = {str(source.source_id) for source in sources}
    capability_ids = {str(capability.cap_id) for capability in capabilities}
    for question in questions:
        if str(question.cap_id) not in capability_ids:
            raise QuestionBankValidationError(
                "question references an unknown capability"
            )
        if not set(map(str, question.source_ids)).issubset(source_ids):
            raise QuestionBankValidationError("question references an unknown source")
    for capability in capabilities:
        variants = {
            question.variant
            for question in questions
            if question.cap_id == capability.cap_id
        }
        if variants != {"positive", "negative"}:
            raise QuestionBankValidationError(
                f"capability {capability.cap_id} requires positive and negative "
                "questions"
            )
    cap_pack_ids = _cap_pack_ids(cap_packs_root)
    for capability in capabilities:
        is_pack = str(capability.cap_id) in cap_pack_ids
        if capability.lifecycle == "runnable" and not is_pack:
            raise QuestionBankValidationError(
                f"runnable capability {capability.cap_id} has no executable cap pack"
            )
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
    _validate_cross_references(
        sources,
        capabilities,
        questions,
        cap_packs_root or root.parent / "cap_packs",
    )
    return QuestionBank(sources=sources, capabilities=capabilities, questions=questions)
