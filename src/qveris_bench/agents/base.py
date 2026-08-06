from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from qveris_bench.models.suite import AgentProtocol


class AgentTrialError(ValueError):
    pass


class ResponsesClient(Protocol):
    async def create(self, **kwargs: object) -> object: ...


ToolInvoker = Callable[[dict[str, object]], Awaitable[object] | object]


@dataclass(frozen=True)
class AgentTrace:
    calls: int
    elapsed_seconds: float
    output_tokens: int
    proposed_arguments: dict[str, object]
    tool_result: object


class AgentTrial:
    def __init__(
        self,
        client: ResponsesClient,
        protocol: AgentProtocol,
        input_schema: dict[str, object],
        invoke: ToolInvoker,
    ) -> None:
        self._client = client
        self._protocol = protocol
        self._input_schema = input_schema
        self._invoke = invoke

    async def run(self, prompt: str) -> AgentTrace:
        started = time.monotonic()
        tool = {
            "type": "function",
            "name": self._protocol.canonical_tool,
            "description": "Execute the frozen canonical provider interface.",
            "parameters": self._input_schema,
            "strict": True,
        }
        response = await asyncio.wait_for(
            self._client.create(
                model=self._protocol.model,
                input=prompt,
                tools=[tool],
                parallel_tool_calls=False,
                tool_choice={"type": "function", "name": self._protocol.canonical_tool},
            ),
            timeout=self._protocol.timeout_seconds,
        )
        call = _function_call(response)
        output_tokens = _output_tokens(response)
        if output_tokens > self._protocol.token_budget:
            raise AgentTrialError("agent trial exceeded frozen token budget")
        if call["name"] != self._protocol.canonical_tool:
            raise AgentTrialError("response called a non-canonical tool")
        try:
            arguments = json.loads(call["arguments"])
        except json.JSONDecodeError as exc:
            raise AgentTrialError("canonical tool arguments are invalid JSON") from exc
        if not isinstance(arguments, dict):
            raise AgentTrialError("canonical tool arguments must be an object")
        _validate_arguments(self._input_schema, arguments)
        result = self._invoke(arguments)
        if hasattr(result, "__await__"):
            result = await asyncio.wait_for(
                result,
                timeout=max(
                    0.001, self._protocol.timeout_seconds - (time.monotonic() - started)
                ),
            )
        elapsed = time.monotonic() - started
        if elapsed > self._protocol.timeout_seconds:
            raise AgentTrialError("agent trial exceeded frozen timeout")
        return AgentTrace(1, elapsed, output_tokens, arguments, result)


def _function_call(response: object) -> dict[str, Any]:
    output = _response_mapping(response).get("output")
    if not isinstance(output, list) or len(output) != 1:
        raise AgentTrialError("agent trial must produce exactly one function call")
    call = output[0]
    if not isinstance(call, dict) or call.get("type") != "function_call":
        raise AgentTrialError("agent trial must produce a function call")
    name = call.get("name")
    arguments = call.get("arguments")
    if not isinstance(name, str) or not isinstance(arguments, str):
        raise AgentTrialError("function call is malformed")
    return {"name": name, "arguments": arguments}


def _output_tokens(response: object) -> int:
    usage = _response_mapping(response).get("usage")
    if not isinstance(usage, dict):
        raise AgentTrialError("response usage is required")
    tokens = usage.get("output_tokens")
    if not isinstance(tokens, int) or tokens < 0:
        raise AgentTrialError("response token usage is malformed")
    return tokens


def _response_mapping(response: object) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    model_dump = getattr(response, "model_dump", None)
    if not callable(model_dump):
        raise AgentTrialError("Responses client returned an unsupported response")
    dumped = model_dump()
    if not isinstance(dumped, dict):
        raise AgentTrialError("Responses client returned an unsupported response")
    return dumped


def _validate_arguments(
    schema: dict[str, object], arguments: dict[str, object]
) -> None:
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise AgentTrialError("frozen tool schema is malformed")
    if not all(isinstance(name, str) and name in arguments for name in required):
        raise AgentTrialError("canonical tool arguments omit a required field")
    if schema.get("additionalProperties") is False and not set(arguments) <= set(
        properties
    ):
        raise AgentTrialError("canonical tool arguments include an unknown field")
    for name, value in arguments.items():
        definition = properties.get(name)
        if not isinstance(definition, dict):
            continue
        expected = definition.get("type")
        valid = (
            expected is None
            or (expected == "string" and isinstance(value, str))
            or (
                expected == "number"
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            )
            or (expected == "boolean" and isinstance(value, bool))
        )
        if not valid:
            raise AgentTrialError(f"canonical tool argument has invalid type: {name}")
