from __future__ import annotations

from pathlib import Path

import pytest

from qveris_bench.cap_packs.sec_filing_evidence.extractors import (
    SecFilingExtractionError,
    extract_fmp_10k,
    extract_fmp_sec_filings,
    extract_massive_stocks_risk_factors,
)
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/sec_filing_evidence"
DIGEST = "sha256:" + "a" * 64


def _massive_document() -> dict[str, object]:
    return {
        "result": {
            "data": {
                "results": [
                    {
                        "ticker": "AAPL",
                        "cik": "0000320193",
                        "filing_date": "2025-10-30",
                        "text": (
                            "We rely on our supply chain for key components; "
                            "disruptions could harm our business."
                        ),
                    }
                ],
                "status": "success",
            }
        }
    }


def _massive_flat_document() -> dict[str, object]:
    return {
        "status": "OK",
        "request_id": "probe-1",
        "results": [
            {
                "cik": "0000320193",
                "ticker": "AAPL",
                "secondary_category": "supply_chain_and_procurement",
                "filing_date": "2024-11-01",
                "supporting_text": (
                    "Restrictions on international trade can materially adversely "
                    "affect the Company's business and supply chain."
                ),
            },
            {
                "cik": "0000320193",
                "ticker": "AAPL",
                "secondary_category": "dividend_policy_and_capital_allocation",
                "filing_date": "2024-11-01",
                "supporting_text": (
                    "Future dividends are subject to declaration by the Board."
                ),
            },
        ],
    }


def _fmp_10k_document() -> dict[str, object]:
    return {
        "symbol": "AAPL",
        "report": {
            "risk_factors": (
                "Our operations depend on a complex global supply chain and "
                "disruptions could adversely affect results."
            )
        },
    }


def _fmp_filings_document() -> dict[str, object]:
    return {
        "filings": [
            {
                "form": "10-K",
                "filingDate": "2025-10-30",
                "accessNumber": "0000320193-25-000123",
                "cik": "0000320193",
                "companyName": "Apple Inc.",
            }
        ]
    }


def test_ac5_massive_stocks_extracts_cited_risk_factor() -> None:
    facts = extract_massive_stocks_risk_factors(_massive_document(), "AAPL")

    assert facts["symbol"] == "AAPL"
    assert facts["filing_id"] == "0000320193-2025-10-30"
    assert "supply chain" in facts["evidence"].lower()
    assert facts["citation"] == "10-K filed 2025-10-30 (CIK 0000320193)"
    extract_observation(PACK / "observation-schema.yaml", facts, DIGEST, "1.0.0")


def test_ac5_massive_flat_envelope_extracts_live_supporting_text() -> None:
    facts = extract_massive_stocks_risk_factors(_massive_flat_document(), "AAPL")

    assert facts["symbol"] == "AAPL"
    assert facts["filing_id"] == "0000320193-2024-11-01"
    assert "supply chain" in facts["evidence"].lower()
    assert facts["citation"] == "10-K filed 2024-11-01 (CIK 0000320193)"
    extract_observation(PACK / "observation-schema.yaml", facts, DIGEST, "1.0.0")


def test_ac5_massive_rows_without_supply_chain_passage_fail_closed() -> None:
    document = {
        "status": "OK",
        "results": [
            {
                "cik": "0000320193",
                "ticker": "AAPL",
                "filing_date": "2024-11-01",
                "supporting_text": "Future dividends are subject to Board approval.",
            }
        ],
    }

    with pytest.raises(SecFilingExtractionError, match="passage"):
        extract_massive_stocks_risk_factors(document, "AAPL")


def test_ac5_massive_error_envelope_is_provider_side_unavailable() -> None:
    document = {
        "error_message": "no risk factors for this request",
        "result": {"data": "not-a-structured-response"},
    }

    with pytest.raises(SecFilingExtractionError, match="unavailable"):
        extract_massive_stocks_risk_factors(document, "AAPL")

    facts = extract_massive_stocks_risk_factors(document, "AAPL", negative_control=True)

    assert facts == {"validation_error": "no risk factors returned"}


def test_ac5_fmp_10k_extracts_cited_passage() -> None:
    facts = extract_fmp_10k(_fmp_10k_document(), "AAPL", 2025)

    assert facts["filing_id"] == "AAPL-10-K-2025"
    assert "supply chain" in facts["evidence"].lower()
    assert facts["citation"] == "10-K fiscal year 2025"


def test_ac5_fmp_filings_search_provides_citation_but_no_passage() -> None:
    with pytest.raises(SecFilingExtractionError, match="passage"):
        extract_fmp_sec_filings(_fmp_filings_document(), "AAPL")


def test_ac5_missing_passage_is_explicitly_unavailable() -> None:
    document = {"result": {"data": {"results": [], "status": "success"}}}
    with pytest.raises(SecFilingExtractionError, match="unavailable"):
        extract_massive_stocks_risk_factors(document, "AAPL")


def test_ac5_negative_control_rejects_passage_substitution() -> None:
    with pytest.raises(SecFilingExtractionError, match="filing type not supported"):
        extract_massive_stocks_risk_factors(
            _massive_document(), "AAPL", negative_control=True
        )
    with pytest.raises(SecFilingExtractionError, match="filing type not supported"):
        extract_fmp_10k(_fmp_10k_document(), "AAPL", 2025, negative_control=True)


def test_ac5_fmp_filings_negative_control_accepts_explicit_negative_state() -> None:
    document = {
        "error_message": "Invalid form type NOTAFILING",
        "filings": [],
    }

    facts = extract_fmp_sec_filings(document, "AAPL", negative_control=True)

    assert facts == {"validation_error": "unsupported filing type"}


def test_ac4_observation_schema_rejects_missing_citation() -> None:
    with pytest.raises(ExtractionError, match="citation"):
        extract_observation(
            PACK / "observation-schema.yaml",
            {"symbol": "AAPL", "filing_id": "x", "evidence": "y"},
            DIGEST,
            "1.0.0",
        )
