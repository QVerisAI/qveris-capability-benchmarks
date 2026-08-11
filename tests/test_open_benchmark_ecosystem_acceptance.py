from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FORMS = ROOT / ".github/ISSUE_TEMPLATE"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _form(path: str) -> dict[str, object]:
    document = yaml.safe_load((FORMS / path).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _field_ids(document: dict[str, object]) -> set[str]:
    body = document["body"]
    assert isinstance(body, list)
    ids = {
        field["id"]
        for field in body
        if isinstance(field, dict) and field.get("type") != "markdown"
    }
    assert len(ids) == len(
        [field for field in body if isinstance(field, dict) and field.get("id")]
    ), "AC7 issue form field IDs must be unique"
    return ids


def test_ac5_single_cap_release_boundary_has_one_strategy_ssot() -> None:
    strategy = _read("docs/product-strategy.md")
    readme = _read("README.md")

    assert "Each benchmark release belongs to exactly one CAP" in strategy
    assert "consume facts from multiple independent CAP releases" in strategy
    assert "[product strategy](docs/product-strategy.md)" in readme


def test_ac7_participant_journeys_link_to_their_operational_entry_points() -> None:
    readme = _read("README.md")
    contributing = _read("CONTRIBUTING.md")
    ecosystem = _read("docs/architecture/open-benchmark-ecosystem.md")

    for target in (
        "docs/release-replay.md",
        "CONTRIBUTING.md",
        "GOVERNANCE.md",
    ):
        assert target in readme, f"README must link {target}"
        assert (ROOT / target).is_file(), f"linked target does not exist: {target}"

    for template in (
        "provider-submission.yml",
        "cap-method-proposal.yml",
        "result-challenge.yml",
    ):
        assert template in contributing, f"CONTRIBUTING must link {template}"

    for journey in ("Developer", "Provider", "Contributor"):
        assert f"## {journey}" in ecosystem, f"missing {journey} journey"


def test_ac6_governance_is_the_policy_ssot() -> None:
    governance = _read("GOVERNANCE.md")
    required_contracts = (
        "provider_submitted",
        "maintainer_verified",
        "community_reproduced",
        "release digest",
        "suite fingerprint",
        "provider_id",
        "access_path_id",
        "conflict of interest",
        "cannot be purchased",
        "successor release",
    )
    missing = [
        contract for contract in required_contracts if contract not in governance
    ]

    assert not missing, f"AC6 missing governance contracts: {missing}"
    for guide in ("CONTRIBUTING.md", "docs/adding-a-provider.md"):
        assert "GOVERNANCE.md" in _read(guide), f"{guide} must link policy SSOT"


def test_ac7_issue_forms_are_structured_for_their_domain_contracts() -> None:
    required_ids = {
        "provider-submission.yml": {
            "provider_id",
            "access_path_id",
            "official_interface",
            "submitter_relationship",
            "disclosure_permission",
            "conflict_of_interest",
        },
        "cap-method-proposal.yml": {
            "developer_decision",
            "cap_boundary",
            "cases",
            "outcome_rules",
            "source_license",
            "conflict_of_interest",
            "no_aggregate",
        },
        "result-challenge.yml": {
            "release_id",
            "release_digest",
            "provider_id",
            "access_path_id",
            "run_key",
            "claim",
            "counter_evidence",
            "conflict_of_interest",
        },
    }

    for filename, expected_ids in required_ids.items():
        document = _form(filename)
        assert document.get("name")
        assert document.get("description")
        assert expected_ids <= _field_ids(document)
        body = document["body"]
        assert isinstance(body, list)
        assert all(
            field.get("type")
            in {"markdown", "input", "textarea", "dropdown", "checkboxes"}
            for field in body
            if isinstance(field, dict)
        )
        assert "Do not include API keys" in (FORMS / filename).read_text(
            encoding="utf-8"
        )


def test_ac7_issue_chooser_routes_security_and_rejects_blank_issues() -> None:
    config = _form("config.yml")

    assert config["blank_issues_enabled"] is False
    links = config["contact_links"]
    assert isinstance(links, list)
    assert any(
        "security" in str(link.get("name", "")).lower()
        for link in links
        if isinstance(link, dict)
    )


def test_ac7_pull_request_template_requires_evidence_and_validation() -> None:
    template = _read(".github/pull_request_template.md")

    for section in (
        "## Scope",
        "## Acceptance criteria",
        "## Evidence and disclosure",
        "## Validation",
    ):
        assert section in template


def test_ac7_roadmap_keeps_live_byok_and_sites_out_of_v1() -> None:
    ecosystem = _read("docs/architecture/open-benchmark-ecosystem.md")

    assert "Offline release replay" in ecosystem
    assert "QVeris Key" in ecosystem
    assert "Native BYOK" in ecosystem
    assert "not implemented in v1" in ecosystem
