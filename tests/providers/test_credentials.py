from __future__ import annotations

import pytest

from qveris_bench.providers.credentials import (
    CredentialReferenceError,
    missing_credential_references,
    validate_credential_reference,
)


def test_ac6_environment_variable_names_are_valid_credential_references() -> None:
    assert validate_credential_reference("FMP_API_KEY") == "FMP_API_KEY", (
        "AC6 valid environment reference must round-trip"
    )


@pytest.mark.parametrize(
    "value",
    [
        "sk-" + "a" * 24,
        "AKIA" + "A" * 16,
        "ghp_" + "b" * 24,
        "literal-secret-value",
    ],
)
def test_ac6_secret_looking_values_are_rejected(value: str) -> None:
    with pytest.raises(CredentialReferenceError):
        validate_credential_reference(value)


def test_ac7_availability_check_returns_names_without_values() -> None:
    environment = {"FMP_API_KEY": "super-secret-value", "OTHER": "present"}

    missing = missing_credential_references(
        ("FMP_API_KEY", "QVERIS_API_KEY"), environment
    )

    assert missing == ("QVERIS_API_KEY",), (
        "AC7 credential check must return only missing reference names"
    )
    assert "super-secret-value" not in repr(missing), (
        "AC7 credential check must never expose values"
    )
