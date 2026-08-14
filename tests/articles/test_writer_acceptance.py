from __future__ import annotations

import json
from pathlib import Path

import pytest

from qveris_bench.articles.writer import (
    EditorialValidationError,
    build_writer_input,
    load_editorial_document,
)

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = (
    ROOT
    / "selection_snapshots/corporate-actions-v2-publication/selection-snapshot.json"
)
PROFILE = (
    ROOT
    / "docs/guides/capability-seo/best-corporate-actions-apis/publication-profile.yaml"
)
EDITORIAL = (
    ROOT / "docs/guides/capability-seo/best-corporate-actions-apis/editorial.json"
)


def test_ac1_writer_input_is_release_backed_and_contains_no_private_raw() -> None:
    built = build_writer_input(SNAPSHOT, PROFILE, ROOT)
    document = json.loads(built.json_bytes)

    assert document["cap_id"] == "corporate-actions"
    assert document["access_path_count"] == 4
    assert document["live_call_count"] == 72
    assert document["markets"] == ["BR", "CN", "DE", "ES", "FR", "HK", "IN", "JP", "US"]
    assert len(document["public_observations"]) == 72
    assert {item["access_path_id"] for item in document["public_observations"]} == {
        "alpha-vantage-corporate-actions-qveris",
        "eodhd-corporate-actions-qveris",
        "massive-stocks-corporate-actions-qveris",
        "twelve-data-corporate-actions-qveris",
    }
    assert any(
        item["facts"].get("ratio") == 4.0 and item["facts"].get("date") == "2020-08-31"
        for item in document["public_observations"]
    )
    serialized = built.json_bytes.decode("utf-8")
    assert "raw_digest" not in serialized
    assert "private" not in serialized.lower()


def test_ac3_editorial_document_rejects_unbound_claims(tmp_path: Path) -> None:
    writer_input = json.loads(build_writer_input(SNAPSHOT, PROFILE, ROOT).json_bytes)
    editorial = {
        "schema_version": 1,
        "skill_id": "cap-article-writer",
        "skill_version": "1.0.0",
        "lead": {
            "copy": "A decision-first explanation.",
            "fact_refs": ["article:scope"],
        },
        "decision_scenarios": [
            {
                "heading": heading,
                "copy": (
                    "Use the selected path when public gateway price is the constraint."
                ),
                "recommended_access_path_ids": [
                    "massive-stocks-corporate-actions-qveris"
                ],
                "fact_refs": [
                    "path:massive-stocks-corporate-actions-qveris:list-price"
                ],
            }
            for heading in (
                "Lowest public gateway list price",
                "Lowest observed gateway latency",
                "Broadest released market evidence",
                "Explicit invalid input handling",
            )
        ],
        "evidence_explainer": {
            "copy": "The contract separates successful samples from missing evidence.",
            "fact_refs": ["article:evidence-states"],
        },
        "cap_explainer": {
            "copy": (
                "A usable event preserves identity, date semantics, "
                "and ratio semantics."
            ),
            "fact_refs": ["article:scope"],
        },
        "chart_explanations": {
            "market": {
                "copy": "Read each cell as a released observation state.",
                "fact_refs": ["article:markets"],
            },
            "tradeoff": {
                "copy": (
                    "Read the axes together and keep the small sample boundary in view."
                ),
                "fact_refs": ["article:runtime-tradeoff"],
            },
        },
        "provider_analyses": [
            {
                "access_path_id": path_id,
                "copy": (
                    "This path should be judged within its released evidence boundary."
                ),
                "fact_refs": [f"path:{path_id}:sample"],
            }
            for path_id in (
                "alpha-vantage-corporate-actions-qveris",
                "eodhd-corporate-actions-qveris",
                "massive-stocks-corporate-actions-qveris",
                "twelve-data-corporate-actions-qveris",
            )
        ],
        "agent_notes": {
            "copy": "Validate identity and normalize failures before downstream use.",
            "fact_refs": ["article:agent-boundary"],
        },
        "limitations": {
            "copy": "Representative cases do not establish universal coverage.",
            "fact_refs": ["article:limitations"],
        },
        "faq": [
            {
                "question": question,
                "answer": "No. Choose by the released decision dimension.",
                "fact_refs": ["article:no-overall-winner"],
            }
            for question in (
                "How should developers choose?",
                "Does a sample prove universal support?",
                "Can developers reproduce the evidence?",
            )
        ],
    }
    editorial = json.loads(EDITORIAL.read_text(encoding="utf-8"))
    editorial_path = tmp_path / "editorial.json"
    editorial_path.write_text(json.dumps(editorial), encoding="utf-8")

    load_editorial_document(editorial_path, writer_input)

    editorial["lead"]["copy"] = (
        "Alpha Vantage costs 999 credits at https://false.example."
    )
    editorial["lead"]["fact_refs"] = ["unknown:fact"]
    editorial_path.write_text(json.dumps(editorial), encoding="utf-8")
    with pytest.raises(EditorialValidationError):
        load_editorial_document(editorial_path, writer_input)


def test_editorial_rejects_wrong_shortlist_links_and_absolute_claims(
    tmp_path: Path,
) -> None:
    writer_input = json.loads(build_writer_input(SNAPSHOT, PROFILE, ROOT).json_bytes)
    original = json.loads(EDITORIAL.read_text(encoding="utf-8"))
    editorial_path = tmp_path / "editorial.json"

    wrong_shortlist = json.loads(json.dumps(original))
    wrong_shortlist["decision_scenarios"][0]["recommended_access_path_ids"] = [
        "alpha-vantage-corporate-actions-qveris"
    ]
    editorial_path.write_text(json.dumps(wrong_shortlist), encoding="utf-8")
    with pytest.raises(EditorialValidationError, match="shortlist"):
        load_editorial_document(editorial_path, writer_input)

    for unsafe_copy in (
        "Read the [source](//false.example) before choosing.",
        "Read the <a href='javascript:alert()'>source</a> before choosing.",
        "This path guarantees flawless pagination and permanent uptime.",
        (
            "The released cohort supports pagination across all historical records; "
            "details are available at false.example/audit."
        ),
    ):
        unsafe = json.loads(json.dumps(original))
        unsafe["lead"]["copy"] = unsafe_copy
        editorial_path.write_text(json.dumps(unsafe), encoding="utf-8")
        with pytest.raises(EditorialValidationError):
            load_editorial_document(editorial_path, writer_input)


def test_editorial_rejects_invalid_input_shortlist_without_positive_evidence(
    tmp_path: Path,
) -> None:
    writer_input = json.loads(build_writer_input(SNAPSHOT, PROFILE, ROOT).json_bytes)
    for row in writer_input["rows"]:
        row["agent_interface"]["invalid_input_handling"] = {
            "state": "measured",
            "passed": 0,
            "total": 3,
        }
    editorial_path = tmp_path / "editorial.json"
    editorial_path.write_bytes(EDITORIAL.read_bytes())

    with pytest.raises(EditorialValidationError, match="no measured facts"):
        load_editorial_document(editorial_path, writer_input)
