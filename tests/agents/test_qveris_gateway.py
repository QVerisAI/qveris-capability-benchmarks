from __future__ import annotations

import pytest

from qveris_bench.agents.base import AgentTrialError
from qveris_bench.agents.gateway import (
    DEFAULT_QVERIS_AI_GATEWAY_BASE_URL,
    qveris_responses_client,
)


def test_ac_qveris_gateway_requires_the_qveris_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QVERIS_API_KEY", raising=False)

    with pytest.raises(AgentTrialError, match="QVERIS_API_KEY"):
        qveris_responses_client()


def test_ac_qveris_gateway_uses_the_configured_openai_compatible_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    class FakeClient:
        responses = object()

        def __init__(self, *, api_key: str, base_url: str) -> None:
            captured.update(api_key=api_key, base_url=base_url)

    monkeypatch.setattr("qveris_bench.agents.gateway.AsyncOpenAI", FakeClient)

    result = qveris_responses_client(api_key="controlled-key")

    assert result is FakeClient.responses
    assert captured == {
        "api_key": "controlled-key",
        "base_url": DEFAULT_QVERIS_AI_GATEWAY_BASE_URL,
    }
