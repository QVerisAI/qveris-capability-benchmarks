from __future__ import annotations

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
        response = await self._client.create(
            model=self._protocol.model,
            input=prompt,
            tools=[tool],
            parallel_tool_calls=False,
        )
        call = _function_call(response)
        if call["name"] != self._protocol.canonical_tool:
            raise AgentTrialError("response called a non-canonical tool")
        arguments = json.loads(call["arguments"])
        if not isinstance(arguments, dict):
            raise AgentTrialError("canonical tool arguments must be an object")
        result = self._invoke(arguments)
        if hasattr(result, "__await__"):
            result = await result
        elapsed = time.monotonic() - started
        if elapsed > self._protocol.timeout_seconds:
            raise AgentTrialError("agent trial exceeded frozen timeout")
        return AgentTrace(1, elapsed, arguments, result)


def _function_call(response: object) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise AgentTrialError("Responses client returned an unsupported response")
    output = response.get("output")
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
