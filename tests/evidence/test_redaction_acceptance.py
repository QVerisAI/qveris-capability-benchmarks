from qveris_bench.evidence.redaction import redact_text


def test_ac1_redaction_removes_secrets_from_transport_artifacts() -> None:
    artifact = (
        "Authorization: Bearer secret-token\n"
        "https://api.example.test/data?api_key=url-secret\n"
        '{"api_key":"body-secret","email":"person@example.com"}\n'
        "upstream error: X-API-Key: error-secret"
    )

    sanitized = redact_text(artifact)

    for secret in ("secret-token", "url-secret", "body-secret", "error-secret"):
        assert secret not in sanitized.text
    assert "person@example.com" not in sanitized.text
    assert "[REDACTED]" in sanitized.text


def test_ac1_redaction_removes_phone_and_account_identifiers() -> None:
    sanitized = redact_text("phone=+1 415-555-0100 account_id=acct_123456789")

    assert "+1 415-555-0100" not in sanitized.text
    assert "acct_123456789" not in sanitized.text
