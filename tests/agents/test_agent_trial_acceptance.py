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
            ],
            "usage": {"output_tokens": 1},
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
        assert "tool_choice" not in client.request

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
                    ],
                    "usage": {"output_tokens": 1},
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


def test_ac1_agent_trial_rejects_token_budget_overrun() -> None:
    async def run() -> None:
        class OverBudget(FakeResponses):
            async def create(self, **kwargs: object) -> object:
                return {
                    "output": [
                        {
                            "type": "function_call",
                            "name": "get-quote",
                            "arguments": "{}",
                        }
                    ],
                    "usage": {"output_tokens": 101},
                }

        protocol = AgentProtocol(
            model="test-model",
            prompt_version="1.0.0",
            canonical_tool="get-quote",
            maximum_calls=1,
            token_budget=100,
            timeout_seconds=10,
        )
        trial = AgentTrial(OverBudget(), protocol, {"type": "object"}, lambda _: None)
        with pytest.raises(AgentTrialError, match="token"):
            await trial.run("Quote AAPL")

    asyncio.run(run())


def test_ac_agent_trial_accepts_openai_sdk_response_objects() -> None:
    class SdkResponse:
        def model_dump(self) -> dict[str, object]:
            return {
                "output": [
                    {
                        "type": "function_call",
                        "name": "get-quote",
                        "arguments": '{"symbol":"AAPL"}',
                    }
                ],
                "usage": {"output_tokens": 1},
            }

    async def run() -> None:
        class SdkClient:
            async def create(self, **kwargs: object) -> object:
                return SdkResponse()

        protocol = AgentProtocol(
            model="test-model",
            prompt_version="1.0.0",
            canonical_tool="get-quote",
            maximum_calls=1,
            token_budget=100,
            timeout_seconds=10,
        )
        trial = AgentTrial(
            SdkClient(),
            protocol,
            {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
                "additionalProperties": False,
            },
            lambda _: {"price": 10},
        )

        assert (await trial.run("Quote AAPL")).proposed_arguments == {"symbol": "AAPL"}

    asyncio.run(run())


def test_ac_agent_trial_allows_reasoning_before_one_canonical_call() -> None:
    class ReasoningClient:
        async def create(self, **kwargs: object) -> object:
            return {
                "output": [
                    {"type": "reasoning"},
                    {
                        "type": "function_call",
                        "name": "get-quote",
                        "arguments": '{"symbol":"AAPL"}',
                    },
                ],
                "usage": {"output_tokens": 1},
            }

    protocol = AgentProtocol(
        model="test-model",
        prompt_version="1.0.0",
        canonical_tool="get-quote",
        maximum_calls=1,
        token_budget=100,
        timeout_seconds=10,
    )

    async def run() -> None:
        trace = await AgentTrial(
            ReasoningClient(),
            protocol,
            {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
                "additionalProperties": False,
            },
            lambda _: {"price": 10},
        ).run("Quote AAPL")
        assert trace.calls == 1

    asyncio.run(run())
