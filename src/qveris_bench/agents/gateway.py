from __future__ import annotations

import os
from typing import cast

from openai import AsyncOpenAI

from qveris_bench.agents.base import AgentTrialError, ResponsesClient

DEFAULT_QVERIS_AI_GATEWAY_BASE_URL = "https://aigateway.qveris.ai/v1"


def qveris_responses_client(
    api_key: str | None = None, base_url: str | None = None
) -> ResponsesClient:
    resolved_key = api_key or os.environ.get("QVERIS_API_KEY")
    if not resolved_key:
        raise AgentTrialError("QVERIS_API_KEY is required for the QVeris AI gateway")
    resolved_base_url = (
        base_url
        or os.environ.get("QVERIS_AI_GATEWAY_BASE_URL")
        or DEFAULT_QVERIS_AI_GATEWAY_BASE_URL
    )
    return cast(
        ResponsesClient,
        AsyncOpenAI(api_key=resolved_key, base_url=resolved_base_url).responses,
    )
