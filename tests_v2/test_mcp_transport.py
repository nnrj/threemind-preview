import asyncio
import sys

import pytest

pytest.importorskip("mcp")


def test_real_stdio_handshake_and_catalog_tools():
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def run():
        async with (
            stdio_client(StdioServerParameters(command=sys.executable, args=["-m", "threemind_lab.mcp_server"])) as (
                read,
                write,
            ),
            ClientSession(read, write, read_timeout_seconds=15) as session,
        ):
            response = await session.initialize()
            assert response.server_info.name == "ThreeMind research tools"
            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            assert names == {
                "operations_list",
                "operation_describe",
                "operation_preflight",
                "operation_call",
                "operation_receipt",
                "bundle_file_transfer",
            }
            calls = next(t for t in listing.tools if t.name == "operation_call")
            assert not calls.annotations.read_only_hint
            assert not calls.annotations.idempotent_hint
            assert next(t for t in listing.tools if t.name == "operation_describe").annotations.read_only_hint

    asyncio.run(run())
