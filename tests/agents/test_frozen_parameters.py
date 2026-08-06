import asyncio

import pytest

from qveris_bench.agents.base import AgentTrial
from qveris_bench.agents.frozen import FrozenAgentInputError, merge_frozen_parameters
from qveris_bench.models.suite import AgentProtocol


def test_ac_agent_can_propose_only_the_frozen_exposed_parameters() -> None:
    assert merge_frozen_parameters(
        {"function": "ETF_PROFILE", "symbol": "SPY"},
        {"symbol": "SPY"},
        ("symbol",),
    ) == {"function": "ETF_PROFILE", "symbol": "SPY"}


def test_ac_agent_rejects_symbol_drift_before_provider_invocation() -> None:
    with pytest.raises(FrozenAgentInputError, match="outside the frozen run"):
        merge_frozen_parameters(
            {"function": "ETF_PROFILE", "symbol": "SPY"},
            {"symbol": "QQQ"},
            ("symbol",),
        )


def test_ac_agent_symbol_drift_does_not_invoke_the_provider() -> None:
    class WrongSymbolClient:
        async def create(self, **kwargs: object) -> object:
            return {
                "output": [
                    {
                        "type": "function_call",
                        "name": "alpha-vantage-etf-profile",
                        "arguments": '{"symbol":"QQQ"}',
                    }
                ],
                "usage": {"output_tokens": 1},
            }

    invoked = False

    async def invoke(arguments: dict[str, object]) -> object:
        nonlocal invoked
        merge_frozen_parameters(
            {"function": "ETF_PROFILE", "symbol": "SPY"}, arguments, ("symbol",)
        )
        invoked = True
        return {}

    protocol = AgentProtocol(
        model="test-model",
        prompt_version="1.0.0",
        canonical_tool="alpha-vantage-etf-profile",
        maximum_calls=1,
        token_budget=100,
        timeout_seconds=10,
    )

    async def run() -> None:
        with pytest.raises(FrozenAgentInputError, match="outside the frozen run"):
            await AgentTrial(
                WrongSymbolClient(),
                protocol,
                {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                    "additionalProperties": False,
                },
                invoke,
            ).run("Retrieve SPY holdings.")

    asyncio.run(run())
    assert not invoked
