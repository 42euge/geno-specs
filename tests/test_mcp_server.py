"""Smoke test for the MCP server's exposed tool surface."""

from __future__ import annotations

import asyncio

from geno_specs.mcp_server import mcp

EXPECTED_TOOLS = {
    "create_spec",
    "list_specs",
    "show_spec",
    "mark_ready",
    "run_spec",
    "validate_spec",
}


def test_tool_list_includes_expected_names():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert EXPECTED_TOOLS <= names
