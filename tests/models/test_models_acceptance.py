from __future__ import annotations

import jsonschema
import pytest
from pydantic import ValidationError

from qveris_bench.models.cap import CapDefinition, SourceReference
from qveris_bench.models.enums import (
    AccessPathType,
    DimensionState,
    FailureAttribution,
    OutcomeStatus,
    ReleaseFactType,
    SourceType,
)
from qveris_bench.models.provider import AccessPath
from qveris_bench.models.release import BenchmarkRelease, ReleaseFact
from qveris_bench.models.run import TaskOutcome
from qveris_bench.models.suite import AgentProtocol


def _harbor_source() -> SourceReference:
    return SourceReference(
        source_type=SourceType.HARBOR_CATALOG,
        harbor_capability_id="MKT.DIVIDENDS",
        contract_version=1,
        catalog_snapshot_digest="a" * 64,
        contract_digest="b" * 64,
    )


def test_ac1_minimal_cap_definition_is_valid() -> None:
    cap = CapDefinition(
        cap_id="dividend-events",
        version="1.0.0",
        name="Dividend Events",
        business_use="Select a provider for dated dividend events.",
        scope=("Dated issuer dividend events",),
        exclusions=("portfolio optimization",),
        markets=("US",),
        asset_types=("EQUITY",),
        sources=(_harbor_source(),),
    )

    assert cap.cap_id == "dividend-events", "AC1 valid CAP must retain its stable ID"


@pytest.mark.parametrize("cap_id", ["ETF_Holdings", "-etf", "etf--holdings", ""])
def test_ac2_invalid_stable_ids_are_rejected(cap_id: str) -> None:
    with pytest.raises(ValidationError, match="cap_id"):
        CapDefinition(
            cap_id=cap_id,
            version="1.0.0",
            name="Dividend Events",
            business_use="Compare constituent-level ETF data.",
            scope=("US ETFs",),
            sources=(_harbor_source(),),
        )


@pytest.mark.parametrize("version", ["1", "v1.0.0", "1.0", "1.0.0.0"])
def test_ac2_invalid_semantic_versions_are_rejected(version: str) -> None:
    with pytest.raises(ValidationError, match="version"):
        CapDefinition(
            cap_id="dividend-events",
            version=version,
            name="Dividend Events",
            business_use="Compare constituent-level ETF data.",
            scope=("US ETFs",),
            sources=(_harbor_source(),),
        )


@pytest.mark.parametrize(
    "missing",
    [
        "harbor_capability_id",
        "contract_version",
        "catalog_snapshot_digest",
        "contract_digest",
    ],
)
def test_ac3_formal_caps_require_pinned_harbor_provenance(missing: str) -> None:
    values = {
        "source_type": SourceType.HARBOR_CATALOG,
        "harbor_capability_id": "MKT.DIVIDENDS",
        "contract_version": 1,
        "catalog_snapshot_digest": "a" * 64,
        "contract_digest": "b" * 64,
    }
    values.pop(missing)

    with pytest.raises(ValidationError, match=missing):
        SourceReference(**values)


def test_ac4_access_path_uses_approved_type_without_credential_reference() -> None:
    access_path = AccessPath(
        access_path_id="fmp-official-api",
        provider_id="financial-modeling-prep",
        path_type=AccessPathType.OFFICIAL_API,
        official_source="https://site.financialmodelingprep.com/developer/docs",
        authorization="Public paid plan permits benchmark execution.",
        canonical_interface="etf-holder",
        protocol="https_rest",
        endpoint_url="https://financialmodelingprep.com/stable",
        authentication="API key query parameter",
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
            authorization="Public paid plan permits benchmark execution.",
            canonical_interface="etf-holder",
            protocol="https_rest",
            endpoint_url="https://financialmodelingprep.com/stable",
            authentication="API key query parameter",
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


def test_ac9_measured_dimension_fact_requires_evidence_reference() -> None:
    with pytest.raises(ValidationError, match="evidence references"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            details={"dimension": "task_completion"},
        )

    ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.MEASURED,
        details={"dimension": "task_completion"},
        evidence_refs=("sha256:" + "a" * 64,),
    )


def test_ac9_declared_dimension_fact_cannot_carry_evidence_reference() -> None:
    with pytest.raises(ValidationError, match="cannot carry evidence"):
        ReleaseFact(
            fact_type=ReleaseFactType.LIMITATION,
            dimension_state=DimensionState.DECLARED,
            details={"dimension": "coverage"},
            evidence_refs=("sha256:" + "a" * 64,),
        )

    ReleaseFact(
        fact_type=ReleaseFactType.LIMITATION,
        dimension_state=DimensionState.DECLARED,
        details={"dimension": "coverage"},
    )


def test_ac9_missing_dimension_state_is_evidence_insufficient() -> None:
    fact = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        details={"dimension": "task_completion"},
    )

    assert fact.dimension_state is None
    assert fact.model_dump()["dimension_state"] is None


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
                    "fact_type": "outcome",
                    "details": {"provider_score": 100},
                },
            ),
        )


def test_ac8_release_fact_rejects_aggregate_fact_type() -> None:
    with pytest.raises(ValidationError, match="provider_score"):
        BenchmarkRelease(
            release_id="etf-holdings-2026-q3-v1",
            version="1.0.0",
            suite_fingerprint="a" * 64,
            run_plan_digest="sha256:" + "b" * 64,
            developer_selection_facts=(
                {"fact_type": "provider_score", "details": {"value": 100}},
            ),
        )


def test_ac8_exported_release_schema_rejects_aggregate_fact_fields() -> None:
    schema = BenchmarkRelease.model_json_schema(mode="validation")
    instance = {
        "release_id": "etf-holdings-2026-q3-v1",
        "version": "1.0.0",
        "suite_fingerprint": "a" * 64,
        "run_plan_digest": "sha256:" + "b" * 64,
        "developer_selection_facts": (
            {"fact_type": "outcome", "details": {"provider_score": 100}},
        ),
    }

    with pytest.raises(jsonschema.ValidationError, match="provider_score"):
        jsonschema.validate(instance, schema)
