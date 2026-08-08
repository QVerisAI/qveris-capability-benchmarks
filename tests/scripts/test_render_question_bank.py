from __future__ import annotations

from pathlib import Path

from scripts.render_question_bank import render

ROOT = Path(__file__).resolve().parents[2]


def test_overview_document_is_in_sync_with_the_bank() -> None:
    rendered = render(ROOT / "question_bank")
    committed = (ROOT / "docs" / "question-bank-overview.md").read_text(
        encoding="utf-8"
    )

    assert rendered == committed
    assert "32 questions" in rendered
    assert "`financial-statement-facts`" in rendered
    assert "`sec-filing-evidence`" in rendered
    assert "Scenario" in rendered
