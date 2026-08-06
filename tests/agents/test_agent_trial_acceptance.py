import asyncio

import pytest

from qveris_bench.agents.base import AgentTrial, AgentTrialError
from qveris_bench.models.suite import AgentProtocol


class FakeResponses:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    async def create(self, **kwargs: object) -> object:
        self.request = kwargs
        return {
            "output": [
                {
                    "type": "function_call",
                    "name": "get-quote",
                    "arguments": '{"symbol":"AAPL"}',
                }
            ]
        }


def test_ac1_agent_trial_receives_exactly_one_canonical_tool() -> None:
    async def run() -> None:
        client = FakeResponses()
        protocol = AgentProtocol(
            model="test-model",
            prompt_version="1.0.0",
            canonical_tool="get-quote",
            maximum_calls=1,
            token_budget=100,
            timeout_seconds=10,
        )

        async def invoke(arguments: dict[str, object]) -> object:
            assert arguments == {"symbol": "AAPL"}
            return {"price": 10}

        trial = AgentTrial(
            client,
            protocol,
            {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
                "additionalProperties": False,
            },
            invoke,
        )
        trace = await trial.run("Quote AAPL")
        assert trace.calls == 1
        assert client.request is not None
        assert client.request["parallel_tool_calls"] is False
        assert len(client.request["tools"]) == 1

    asyncio.run(run())


def test_ac1_agent_trial_rejects_an_unexpected_tool() -> None:
    async def run() -> None:
        class WrongTool(FakeResponses):
            async def create(self, **kwargs: object) -> object:
                return {
                    "output": [
                        {
                            "type": "function_call",
                            "name": "search-tools",
                            "arguments": "{}",
                        }
                    ]
                }

        protocol = AgentProtocol(
            model="test-model",
            prompt_version="1.0.0",
            canonical_tool="get-quote",
            maximum_calls=1,
            token_budget=100,
            timeout_seconds=10,
        )
        trial = AgentTrial(WrongTool(), protocol, {"type": "object"}, lambda _: None)
        with pytest.raises(AgentTrialError, match="canonical"):
            await trial.run("Quote AAPL")

    asyncio.run(run())
