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
    assert "12 questions" in rendered
    assert "`dividend-events`" in rendered
    assert "`realtime-financial-news`" in rendered
    assert "Scenario role requirements" not in rendered
