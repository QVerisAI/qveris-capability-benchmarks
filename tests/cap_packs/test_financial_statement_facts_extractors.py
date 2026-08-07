from __future__ import annotations

from pathlib import Path

import pytest

from qveris_bench.cap_packs.financial_statement_facts.extractors import (
    FinancialStatementExtractionError,
    extract_alpha_vantage_income_statement,
    extract_fmp_income_statement,
    extract_sec_company_facts,
)
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/financial_statement_facts"
DIGEST = "sha256:" + "a" * 64


def _fmp_document() -> dict[str, object]:
    return {
        "symbol": "AAPL",
        "annualReports": [
            {"date": "2025-09-27", "revenue": 391035000000},
            {"date": "2024-09-28", "revenue": 383285000000},
        ],
    }


def _alpha_vantage_document() -> dict[str, object]:
    return {
        "symbol": "AAPL",
        "annualReports": [
            {"fiscalDateEnding": "2025-09-27", "totalRevenue": "391035000000"},
            {"fiscalDateEnding": "2024-09-28", "totalRevenue": "383285000000"},
        ],
    }


def _sec_document() -> dict[str, object]:
    return {
        "cik": 320193,
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "units": {
                        "USD": [
                            {
                                "start": "2024-09-29",
                                "end": "2025-09-27",
                                "val": 391035000000,
                                "form": "10-K",
                                "fy": 2025,
                            },
                            {
                                "start": "2023-09-30",
                                "end": "2024-09-28",
                                "val": 383285000000,
                                "form": "10-K",
                                "fy": 2024,
                            },
                        ]
                    }
                }
            }
        },
    }


def test_ac5_fmp_extracts_fy2025_revenue() -> None:
    facts = extract_fmp_income_statement(_fmp_document(), "AAPL", 2025)

    assert facts["symbol"] == "AAPL"
    assert facts["fiscal_year"] == "2025"
    assert facts["revenue"] == 391035000000
    assert facts["currency"] == "USD"
    observation = extract_observation(
        PACK / "observation-schema.yaml", facts, DIGEST, "1.0.0"
    )
    assert observation.facts["revenue"] == 391035000000


def test_ac5_fmp_list_envelope_extracts_fy2025_revenue() -> None:
    document = {"result": {"data": _fmp_document()["annualReports"]}}

    facts = extract_fmp_income_statement(document, "AAPL", 2025)

    assert facts["revenue"] == 391035000000


def test_ac5_alpha_vantage_extracts_fy2025_revenue() -> None:
    facts = extract_alpha_vantage_income_statement(
        _alpha_vantage_document(), "AAPL", 2025
    )

    assert facts["fiscal_year"] == "2025"
    assert facts["revenue"] == 391035000000


def test_ac5_sec_company_facts_extracts_fy2025_revenue() -> None:
    facts = extract_sec_company_facts(_sec_document(), "AAPL", 2025)

    assert facts["fiscal_year"] == "2025"
    assert facts["revenue"] == 391035000000
    assert facts["currency"] == "USD"
    assert facts["filing_date"] == "2025-09-27"


def test_ac5_invalid_period_is_explicitly_unavailable_for_all_providers() -> None:
    with pytest.raises(FinancialStatementExtractionError, match="unavailable"):
        extract_fmp_income_statement(_fmp_document(), "AAPL", 1900)
    with pytest.raises(FinancialStatementExtractionError, match="unavailable"):
        extract_alpha_vantage_income_statement(_alpha_vantage_document(), "AAPL", 1900)
    with pytest.raises(FinancialStatementExtractionError, match="unavailable"):
        extract_sec_company_facts(_sec_document(), "AAPL", 1900)


def test_ac5_negative_control_returns_validation_error_for_missing_period() -> None:
    facts = extract_fmp_income_statement(
        _fmp_document(), "AAPL", 1900, negative_control=True
    )

    assert facts == {"validation_error": "fiscal year unavailable"}


def test_ac4_observation_schema_rejects_missing_revenue() -> None:
    with pytest.raises(ExtractionError, match="revenue"):
        extract_observation(
            PACK / "observation-schema.yaml",
            {"symbol": "AAPL", "fiscal_year": "2025"},
            DIGEST,
            "1.0.0",
        )
