"""LangGraph agent with MCP tool integration using langchain-mcp-adapters."""

import os
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.client.auth import OAuthClientProvider


@dataclass
class AgentConfig:
    """Configuration for the MCP agent."""

    mcp_url: str
    provider: str = "anthropic"
    model: str | None = None
    auth_header: str | None = None
    oauth_provider: OAuthClientProvider | None = None

    def __post_init__(self):
        # Set default models based on provider
        if self.model is None:
            if self.provider == "anthropic":
                self.model = "claude-sonnet-4-20250514"
            elif self.provider == "openai":
                self.model = "gpt-4o"
            else:
                raise ValueError(f"Unknown provider: {self.provider}")


def get_model_string(provider: str, model: str) -> str:
    """Get the model string for create_agent."""
    if provider == "anthropic":
        # Verify API key is set
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required for Anthropic provider"
            )
        return model
    elif provider == "openai":
        # Verify API key is set
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for OpenAI provider"
            )
        return f"openai:{model}"
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'anthropic' or 'openai'.")


async def run_agent_session(
    config: AgentConfig,
    on_ready,
):
    """
    Run an agent session with the MCP server using MultiServerMCPClient.
    
    Args:
        config: Agent configuration
        on_ready: Callback function called with (agent, client, tools) when ready
    """
    # Build connection configuration for MultiServerMCPClient
    mcp_config = {
        "mcp_server": {
            "transport": "http",
            "url": config.mcp_url,
        }
    }
    
    # Add authentication if provided
    if config.auth_header:
        mcp_config["mcp_server"]["headers"] = {
            "Authorization": config.auth_header
        }
    
    if config.oauth_provider:
        mcp_config["mcp_server"]["auth"] = config.oauth_provider

    # Create the MultiServerMCPClient
    client = MultiServerMCPClient(mcp_config)
    
    # Get tools from MCP server
    tools = await client.get_tools()
    
    if not tools:
        print("⚠️  No tools found on MCP server")
    else:
        print(f"✓ Loaded {len(tools)} tool(s) from MCP server")
        for tool in tools:
            desc = tool.description or ""
            if len(desc) > 60:
                desc = desc[:60] + "..."
            print(f"  • {tool.name}: {desc}")

    # Get model string and create agent using create_agent
    model_string = get_model_string(config.provider, config.model)
    agent = create_agent(model_string, tools)
    
    print()
    
    # Call the ready callback with agent, client, and tools
    await on_ready(agent, client, tools)
