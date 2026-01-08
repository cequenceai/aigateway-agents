#!/usr/bin/env python3
"""
Tests for MCP server integration with OpenAI Agent.

These tests require an MCP server to be running.
"""

import asyncio
import os
import pytest
from agents import Agent, Runner

from mcp_config import build_mcp_server
from auth.oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage


@pytest.fixture
def api_key():
    """Ensure API key is set."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    return api_key


@pytest.mark.asyncio
async def test_mcp_server_connection(api_key):
    """Test basic MCP server connection."""
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        pytest.skip("MCP_SERVER_URL not set")
    
    # Set up OAuth
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    storage = InMemoryTokenStorage(reset_tokens=False)
    callback_server = CallbackServer(port=3030)
    callback_server.start()
    oauth_provider = create_oauth_provider(base_url, callback_server, reset_tokens=False)
    
    try:
        mcp_server = await build_mcp_server(
            mcp_url=mcp_url,
            oauth_provider=oauth_provider,
            storage=storage
        )
        
        # Connect to server
        await mcp_server.connect()
        
        # Test connection by checking if server is connected
        assert mcp_server is not None
        
        # Cleanup
        await mcp_server.cleanup()
    finally:
        callback_server.stop()


@pytest.mark.asyncio
async def test_mcp_tool_discovery(api_key):
    """Test discovering tools from MCP server."""
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        pytest.skip("MCP_SERVER_URL not set")
    
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    storage = InMemoryTokenStorage(reset_tokens=False)
    callback_server = CallbackServer(port=3030)
    callback_server.start()
    oauth_provider = create_oauth_provider(base_url, callback_server, reset_tokens=False)
    
    try:
        mcp_server = await build_mcp_server(
            mcp_url=mcp_url,
            oauth_provider=oauth_provider,
            storage=storage
        )
        
        await mcp_server.connect()
        
        # Create agent with MCP server
        agent = Agent(
            name="Test Agent",
            instructions="You are a helpful assistant.",
            mcp_servers=[mcp_server]
        )
        
        # Query to discover tools
        result = await Runner.run(
            agent,
            "List all available tools from the MCP server"
        )
        
        assert result is not None
        assert result.final_output is not None
        
        await mcp_server.cleanup()
    finally:
        callback_server.stop()


@pytest.mark.asyncio
async def test_mcp_tool_usage(api_key):
    """Test using a tool from MCP server."""
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        pytest.skip("MCP_SERVER_URL not set")
    
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    storage = InMemoryTokenStorage(reset_tokens=False)
    callback_server = CallbackServer(port=3030)
    callback_server.start()
    oauth_provider = create_oauth_provider(base_url, callback_server, reset_tokens=False)
    
    try:
        mcp_server = await build_mcp_server(
            mcp_url=mcp_url,
            oauth_provider=oauth_provider,
            storage=storage
        )
        
        await mcp_server.connect()
        
        agent = Agent(
            name="Test Agent",
            instructions="You are a helpful assistant with access to MCP server tools.",
            mcp_servers=[mcp_server]
        )
        
        # Try to use a tool
        result = await Runner.run(
            agent,
            "Use the available tools from the MCP server to demonstrate functionality. List the first 3 items you can access."
        )
        
        assert result is not None
        assert result.final_output is not None
        
        await mcp_server.cleanup()
    finally:
        callback_server.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
