import asyncio

import pytest

from qveris_bench.execution.streamable_mcp import (
    build_authorization_headers,
    build_bearer_headers,
)


def test_ac1_streamable_mcp_uses_a_bearer_header() -> None:
    assert build_bearer_headers("test-key") == {"Authorization": "Bearer test-key"}


def test_ac1_streamable_mcp_supports_provider_issued_raw_authorization() -> None:
    assert build_authorization_headers("provider-token", bearer=False) == {
        "Authorization": "provider-token"
    }


@pytest.mark.parametrize("api_key", ("", "   "))
def test_ac1_streamable_mcp_rejects_blank_credentials(api_key: str) -> None:
    async def run() -> None:
        from qveris_bench.execution.streamable_mcp import streamable_mcp_session

        with pytest.raises(ValueError, match="api key"):
            async with streamable_mcp_session("https://example.test/mcp", api_key):
                pass

    asyncio.run(run())


def test_ac1_streamable_mcp_rejects_non_https_endpoint() -> None:
    async def run() -> None:
        from qveris_bench.execution.streamable_mcp import streamable_mcp_session

        with pytest.raises(ValueError, match="HTTPS"):
            async with streamable_mcp_session("http://example.test/mcp", "test-key"):
                pass

    asyncio.run(run())
