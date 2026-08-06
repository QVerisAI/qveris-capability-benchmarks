from __future__ import annotations

import pytest
from pydantic import ValidationError

from qveris_bench.models.cap import CapDefinition, SourceReference
from qveris_bench.models.enums import (
    AccessPathType,
    FailureAttribution,
    OutcomeStatus,
    SourceType,
)
from qveris_bench.models.provider import AccessPath
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import TaskOutcome
from qveris_bench.models.suite import AgentProtocol


def _external_source() -> SourceReference:
    return SourceReference(
        source_type=SourceType.EXTERNAL_REPOSITORY,
        repository="https://github.com/QVerisAI/qveris-agent-harness",
        commit="95179a8",
        task_id="etf-holdings-001",
    )


def test_ac1_minimal_cap_definition_is_valid() -> None:
    cap = CapDefinition(
        cap_id="etf-holdings",
        version="1.0.0",
        name="ETF Holdings",
        business_use="Select a provider for constituent-level ETF analysis.",
        scope=("US-listed ETFs",),
        exclusions=("portfolio optimization",),
        markets=("US",),
        asset_types=("ETF",),
        sources=(_external_source(),),
    )

    assert cap.cap_id == "etf-holdings", "AC1 valid CAP must retain its stable ID"


@pytest.mark.parametrize("cap_id", ["ETF_Holdings", "-etf", "etf--holdings", ""])
def test_ac2_invalid_stable_ids_are_rejected(cap_id: str) -> None:
    with pytest.raises(ValidationError, match="cap_id"):
        CapDefinition(
            cap_id=cap_id,
            version="1.0.0",
            name="ETF Holdings",
            business_use="Compare constituent-level ETF data.",
            scope=("US ETFs",),
            sources=(_external_source(),),
        )


@pytest.mark.parametrize("version", ["1", "v1.0.0", "1.0", "1.0.0.0"])
def test_ac2_invalid_semantic_versions_are_rejected(version: str) -> None:
    with pytest.raises(ValidationError, match="version"):
        CapDefinition(
            cap_id="etf-holdings",
            version=version,
            name="ETF Holdings",
            business_use="Compare constituent-level ETF data.",
            scope=("US ETFs",),
            sources=(_external_source(),),
        )


@pytest.mark.parametrize("missing", ["repository", "commit", "task_id"])
def test_ac3_external_sources_require_pinned_provenance(missing: str) -> None:
    values = {
        "source_type": SourceType.EXTERNAL_REPOSITORY,
        "repository": "https://github.com/example/source",
        "commit": "abc1234",
        "task_id": "task-1",
    }
    values.pop(missing)

    with pytest.raises(ValidationError, match=missing):
        SourceReference(**values)


def test_ac4_access_path_uses_approved_type_and_env_name_only() -> None:
    access_path = AccessPath(
        access_path_id="fmp-official-api",
        provider_id="financial-modeling-prep",
        path_type=AccessPathType.OFFICIAL_API,
        credential_env=("FMP_API_KEY",),
        official_source="https://site.financialmodelingprep.com/developer/docs",
        canonical_interface="etf-holder",
        agent_trial_eligible=False,
    )

    assert access_path.path_type is AccessPathType.OFFICIAL_API, (
        "AC4 approved Access Path type must round-trip"
    )

    with pytest.raises(ValidationError, match="credential_env"):
        AccessPath(
            access_path_id="fmp-official-api",
            provider_id="financial-modeling-prep",
            path_type=AccessPathType.OFFICIAL_API,
            credential_env=("actual-secret-value",),
            official_source="https://site.financialmodelingprep.com/developer/docs",
            canonical_interface="etf-holder",
            agent_trial_eligible=False,
        )


def test_ac5_outcome_and_failure_taxonomy_reject_unapproved_values() -> None:
    outcome = TaskOutcome(
        status=OutcomeStatus.FAILED,
        evidence_refs=("sha256:" + "a" * 64,),
        unmet_conditions=("complete holdings list",),
        failure_attribution=FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    )
    assert outcome.status is OutcomeStatus.FAILED, "AC5 approved outcome must validate"

    with pytest.raises(ValidationError):
        TaskOutcome(
            status="failed",
            evidence_refs=("sha256:" + "a" * 64,),
            unmet_conditions=("complete holdings list",),
            failure_attribution="wrong_tool_selected",
        )


def test_ac6_frozen_inputs_fail_closed_on_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="score"):
        TaskOutcome(
            status=OutcomeStatus.COMPLETED,
            evidence_refs=("sha256:" + "a" * 64,),
            score=100,
        )


def test_ac7_agent_protocol_exposes_one_canonical_tool_without_discovery() -> None:
    protocol = AgentProtocol(
        model="gpt-test",
        prompt_version="1.0.0",
        canonical_tool="get-etf-holdings",
        maximum_calls=3,
        token_budget=2_000,
        timeout_seconds=60,
    )
    assert protocol.canonical_tool == "get-etf-holdings", (
        "AC7 protocol must retain exactly one frozen tool"
    )

    with pytest.raises(ValidationError, match="tools"):
        AgentProtocol(
            model="gpt-test",
            prompt_version="1.0.0",
            canonical_tool="get-etf-holdings",
            maximum_calls=3,
            token_budget=2_000,
            timeout_seconds=60,
            tools=("get-etf-holdings", "search-tools"),
        )


def test_ac8_release_contract_exposes_stage_five_and_six_facts_without_scores() -> None:
    release = BenchmarkRelease(
        release_id="etf-holdings-2026-q3-v1",
        version="1.0.0",
        suite_fingerprint="a" * 64,
        run_plan_digest="sha256:" + "b" * 64,
        developer_selection_facts=(),
        provider_feedback_facts={},
    )

    assert release.developer_selection_facts == (), (
        "AC8 Stage 5 input must be machine-readable facts"
    )
    assert release.provider_feedback_facts == {}, (
        "AC8 Stage 6 input must be machine-readable facts"
    )

    with pytest.raises(ValidationError, match="provider_score"):
        BenchmarkRelease(
            release_id="etf-holdings-2026-q3-v1",
            version="1.0.0",
            suite_fingerprint="a" * 64,
            run_plan_digest="sha256:" + "b" * 64,
            provider_score=99,
        )


def test_ac8_release_fact_details_reject_nested_aggregate_fields() -> None:
    with pytest.raises(ValidationError, match="provider_score"):
        BenchmarkRelease(
            release_id="etf-holdings-2026-q3-v1",
            version="1.0.0",
            suite_fingerprint="a" * 64,
            run_plan_digest="sha256:" + "b" * 64,
            developer_selection_facts=(
                {
                    "fact_type": "provider-observation",
                    "details": {"provider_score": 100},
                },
            ),
        )
