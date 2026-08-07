from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ac1_readme_leads_with_financial_agent_provider_selection() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "financial Agent developers" in readme, (
        "AC1 README must name the primary developer audience"
    )
    assert "provider and Access Path" in readme, (
        "AC1 README must name the developer selection decision"
    )


def test_ac2_strategy_separates_product_and_measurement_units() -> None:
    strategy = (ROOT / "docs/product-strategy.md").read_text(encoding="utf-8")

    assert "Financial Task is the product unit" in strategy, (
        "AC2 strategy must define the external product unit"
    )
    assert "CAP is the measurement unit" in strategy, (
        "AC2 strategy must preserve atomic evaluation"
    )
    assert "Financial Task -> required CAPs" in strategy, (
        "AC2 strategy must define the task-to-evidence chain"
    )


def test_ac3_agent_friendliness_is_observable_and_not_a_score() -> None:
    strategy = (ROOT / "docs/product-strategy.md").read_text(encoding="utf-8")

    required_observations = (
        "single-tool task closure",
        "parameter contract",
        "response schema",
        "error recoverability",
        "pagination and truncation",
        "language mapping",
    )
    missing = [item for item in required_observations if item not in strategy]

    assert not missing, f"AC3 missing Agent-interface observations: {missing}"
    assert "no Agent-friendly composite score" in strategy, (
        "AC3 must prohibit an Agent-friendly aggregate rating"
    )


def test_ac4_strategy_covers_developer_selection_dimensions() -> None:
    strategy = (ROOT / "docs/product-strategy.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs/architecture/platform.md").read_text(encoding="utf-8")

    dimensions = (
        "accuracy",
        "precision",
        "latency",
        "reliability",
        "cost",
        "country and market coverage",
        "language coverage",
        "Agent interface",
    )
    missing = [dimension for dimension in dimensions if dimension not in strategy]

    assert not missing, f"AC4 missing developer selection dimensions: {missing}"
    assert "target selection schema" in strategy, (
        "AC4 future dimensions must not be presented as current v1 facts"
    )
    assert "must remain unavailable or evidence-insufficient" in strategy, (
        "AC4 unsupported dimensions must fail closed"
    )
    assert "target task-fit profile" in readme, (
        "AC4 README must distinguish the product target from current evidence"
    )
    assert "target selection dimensions" in architecture, (
        "AC4 architecture must not overclaim current measurement coverage"
    )


def test_ac5_direct_and_agent_evidence_remain_separate() -> None:
    strategy = (ROOT / "docs/product-strategy.md").read_text(encoding="utf-8")

    assert "Direct Test establishes provider-interface facts" in strategy, (
        "AC5 Direct Test must remain the provider fact source"
    )
    assert "one predetermined canonical tool" in strategy, (
        "AC5 Agent Trial must remain single-tool and predetermined"
    )
    assert "no context-free best provider" in strategy, (
        "AC5 strategy must prohibit a global provider winner"
    )
