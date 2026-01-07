"""Agent setup and execution using OpenAI Agents SDK."""

import logging
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable

from agents import Agent
from agents.mcp import MCPServerStreamableHttp
from mcp.client.auth import OAuthClientProvider

from ..mcp_config import build_mcp_server

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the OpenAI agent."""

    mcp_url: str
    model: str = "gpt-4o"
    auth_header: Optional[str] = None
    oauth_provider: Optional[OAuthClientProvider] = None
    storage = None  # TokenStorage type
    instructions: str = "You are a helpful assistant with access to MCP server tools. Use the available tools to help users accomplish their tasks."


async def create_agent(config: AgentConfig) -> tuple[Agent, MCPServerStreamableHttp]:
    """
    Create an OpenAI Agent with MCP server.
    
    Args:
        config: Agent configuration
        
    Returns:
        Tuple of (Agent instance, MCP server instance)
    """
    logger.info("Creating OpenAI Agent with MCP server...")
    
    # Build MCP server
    mcp_server = await build_mcp_server(
        mcp_url=config.mcp_url,
        auth_header=config.auth_header,
        oauth_provider=config.oauth_provider,
        storage=config.storage,
    )
    
    # Connect to MCP server
    await mcp_server.connect()
    logger.info("✓ Connected to MCP server")
    
    # Create agent with MCP server
    agent = Agent(
        name="OpenAI Agent",
        instructions=config.instructions,
        model=config.model,
        mcp_servers=[mcp_server],
    )
    
    logger.info("✓ Agent created successfully")
    
    return agent, mcp_server


async def run_agent_session(
    config: AgentConfig,
    on_ready: Callable[[Agent, MCPServerStreamableHttp], Awaitable[None]],
):
    """
    Run an agent session with the MCP server.
    
    Args:
        config: Agent configuration
        on_ready: Callback function called with (agent, mcp_server) when ready
    """
    agent = None
    mcp_server = None
    
    try:
        agent, mcp_server = await create_agent(config)
        await on_ready(agent, mcp_server)
    finally:
        # Cleanup MCP server connection
        if mcp_server:
            try:
                await mcp_server.cleanup()
                logger.info("✓ MCP server cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up MCP server: {e}")
