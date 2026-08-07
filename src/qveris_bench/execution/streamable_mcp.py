from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def build_bearer_headers(api_key: str) -> dict[str, str]:
    if not api_key.strip():
        raise ValueError("MCP api key must not be blank")
    return {"Authorization": f"Bearer {api_key}"}


@asynccontextmanager
async def streamable_mcp_session(
    endpoint: str, api_key: str
) -> AsyncIterator[ClientSession]:
    if not endpoint.startswith("https://"):
        raise ValueError("MCP endpoint must use HTTPS")
    async with httpx2.AsyncClient(headers=build_bearer_headers(api_key)) as client:
        async with streamable_http_client(endpoint, http_client=client) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                yield session
