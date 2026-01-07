#!/usr/bin/env python3
"""
Tests for MCP server integration with Claude Agent SDK.

These tests require an MCP server to be running.
"""

import asyncio
import os
import pytest
from claude_agent_sdk import query, ClaudeAgentOptions


@pytest.fixture
def api_key():
    """Ensure API key is set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return api_key


@pytest.mark.asyncio
async def test_mcp_server_basic(api_key):
    """Test basic MCP server connection (if configured)."""
    # This test requires MCP server configuration
    # Skip if not configured
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        pytest.skip("MCP_SERVER_URL not set")
    
    # Build MCP server config
    mcp_servers = {
        "mcp_server": {
            "transport": "http",
            "url": mcp_url,
        }
    }
    
    # Add auth header if provided
    auth_header = os.environ.get("MCP_AUTH_HEADER")
    if auth_header:
        mcp_servers["mcp_server"]["headers"] = {
            "Authorization": auth_header
        }
    
    options = ClaudeAgentOptions(
        mcp_servers=mcp_servers,
        permission_mode="acceptEdits",
        max_turns=5
    )
    
    messages = []
    async for message in query(
        prompt="List all available tools from the MCP server.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_mcp_tool_discovery(api_key):
    """Test discovering tools from MCP server."""
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        pytest.skip("MCP_SERVER_URL not set")
    
    mcp_servers = {
        "mcp_server": {
            "transport": "http",
            "url": mcp_url,
        }
    }
    
    auth_header = os.environ.get("MCP_AUTH_HEADER")
    if auth_header:
        mcp_servers["mcp_server"]["headers"] = {
            "Authorization": auth_header
        }
    
    options = ClaudeAgentOptions(
        mcp_servers=mcp_servers,
        permission_mode="acceptEdits",
        max_turns=3
    )
    
    messages = []
    async for message in query(
        prompt="What tools are available from the MCP server? List their names.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_mcp_tool_usage(api_key):
    """Test using a tool from MCP server."""
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        pytest.skip("MCP_SERVER_URL not set")
    
    mcp_servers = {
        "mcp_server": {
            "transport": "http",
            "url": mcp_url,
        }
    }
    
    auth_header = os.environ.get("MCP_AUTH_HEADER")
    if auth_header:
        mcp_servers["mcp_server"]["headers"] = {
            "Authorization": auth_header
        }
    
    options = ClaudeAgentOptions(
        mcp_servers=mcp_servers,
        permission_mode="acceptEdits",
        max_turns=5
    )
    
    # This is a generic test - adjust the prompt based on your MCP server's tools
    messages = []
    async for message in query(
        prompt="Use any available tool from the MCP server to demonstrate it works.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
