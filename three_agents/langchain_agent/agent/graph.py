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
    storage=None,
):
    """
    Run an agent session with the MCP server using MultiServerMCPClient.
    
    Args:
        config: Agent configuration
        on_ready: Callback function called with (agent, client, tools) when ready
        storage: Optional token storage to check for existing tokens
    """
    # Pre-handle OAuth like Claude agent does - check for existing tokens first
    auth_token = None
    
    # If we have a static auth header, use it
    if config.auth_header:
        if config.auth_header.startswith("Bearer "):
            auth_token = config.auth_header[7:]  # Remove "Bearer " prefix
        else:
            auth_token = config.auth_header
        print("🔑 Using static auth header")
    # Otherwise, check storage for existing tokens
    elif storage:
        try:
            tokens = await storage.get_tokens()
            if tokens and tokens.access_token:
                auth_token = tokens.access_token
                print(f"✓ Found existing OAuth token in storage (length: {len(auth_token)})")
        except Exception as e:
            print(f"⚠ Could not load tokens from storage: {e}")
    
    # If no token found and we have OAuth provider, trigger OAuth registration
    if not auth_token and config.oauth_provider:
        print("⚠ No token found - triggering OAuth registration...")
        try:
            # Use MultiServerMCPClient to trigger OAuth (like Claude agent does)
            temp_config = {
                "mcp_server": {
                    "transport": "http",
                    "url": config.mcp_url,
                    "auth": config.oauth_provider,
                }
            }
            temp_client = MultiServerMCPClient(temp_config)
            await temp_client.get_tools()  # This triggers OAuth registration and flow
            
            # Now get the token from storage
            if storage:
                tokens = await storage.get_tokens()
                if tokens and tokens.access_token:
                    auth_token = tokens.access_token
                    print(f"✓ OAuth registration successful - token obtained (length: {len(auth_token)})")
            
            # Clean up temp client
            try:
                await temp_client.close()
            except:
                pass
        except Exception as e:
            print(f"⚠ Error triggering OAuth: {type(e).__name__}: {str(e)[:200]}")
    
    # Build connection configuration for MultiServerMCPClient
    mcp_config = {
        "mcp_server": {
            "transport": "http",
            "url": config.mcp_url,
        }
    }
    
    # Use token in headers if we have one (preferred method)
    if auth_token:
        mcp_config["mcp_server"]["headers"] = {
            "Authorization": f"Bearer {auth_token}"
        }
        print("🔑 Using token in Authorization header")
    # Fallback: if we have OAuth provider but no token, let MultiServerMCPClient handle it
    elif config.oauth_provider:
        mcp_config["mcp_server"]["auth"] = config.oauth_provider
        print("🔐 OAuth authentication will be handled by MultiServerMCPClient")
    # Fallback: use static auth header if provided
    elif config.auth_header:
        mcp_config["mcp_server"]["headers"] = {
            "Authorization": config.auth_header
        }
        print("🔑 Using static auth header")

    # Create the MultiServerMCPClient with connection optimizations
    client = MultiServerMCPClient(mcp_config)
    
    # Get tools from MCP server with timeout and retry logic for faster connection
    import asyncio
    max_retries = 3
    retry_delay = 2.0  # Start with 2 second delay
    timeout = 60.0  # Increased timeout to 60s per attempt (OAuth flows and slow connections need more time)
    
    print(f"🔗 Connecting to MCP server: {config.mcp_url}")
    if config.oauth_provider:
        print("🔐 OAuth authentication enabled")
    if config.auth_header:
        print("🔑 Static auth header provided")
    
    for attempt in range(max_retries):
        try:
            print(f"⏳ Attempt {attempt + 1}/{max_retries}: Fetching tools from MCP server...")
            # Use timeout per attempt, but allow retries
            tools = await asyncio.wait_for(client.get_tools(), timeout=timeout)
            print(f"✓ Successfully fetched {len(tools)} tool(s) from MCP server")
            break  # Success, exit retry loop
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                print(f"⚠️  Attempt {attempt + 1} timed out after {timeout}s. Retrying in {retry_delay * (attempt + 1):.1f}s...")
                # Exponential backoff for retries
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                error_msg = f"MCP server get_tools() timed out after {max_retries} attempts ({timeout * max_retries:.0f}s total). Server may be unresponsive or network is slow."
                print(f"❌ {error_msg}")
                raise TimeoutError(error_msg)
        except ExceptionGroup as eg:
            # Handle ExceptionGroup (Python 3.11+) - extract underlying exceptions
            error_details = []
            auth_error = False
            for exc in eg.exceptions:
                exc_str = str(exc)
                error_details.append(f"{type(exc).__name__}: {exc_str}")
                # Check for authentication errors (401, 403, unauthorized)
                if any(keyword in exc_str.lower() for keyword in ['401', '403', 'unauthorized', 'forbidden', 'authentication']):
                    auth_error = True
            
            error_msg = f"Connection error (attempt {attempt + 1}/{max_retries}): {'; '.join(error_details)}"
            print(f"❌ {error_msg}")
            
            # Don't retry on authentication errors - fail fast with clear message
            if auth_error:
                auth_msg = "MCP server requires authentication (OAuth or auth header). "
                if not config.oauth_provider and not config.auth_header:
                    auth_msg += "Please configure OAuth or provide an auth header."
                else:
                    auth_msg += "Authentication may have failed or expired."
                print(f"🔐 {auth_msg}")
                # Re-raise the first exception from the group
                if eg.exceptions:
                    raise RuntimeError(auth_msg) from eg.exceptions[0]
                raise RuntimeError(auth_msg)
            
            # Check if any exception suggests a retryable error
            retryable_keywords = ['connection', 'timeout', 'network', 'unreachable', 'refused', '500', '502', '503', '504']
            is_retryable = any(
                any(keyword in str(exc).lower() for keyword in retryable_keywords)
                for exc in eg.exceptions
            )
            
            if attempt < max_retries - 1 and is_retryable:
                print(f"⚠️  Retrying in {retry_delay * (attempt + 1):.1f}s...")
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                # Re-raise the first exception from the group for better error reporting
                if eg.exceptions:
                    raise eg.exceptions[0] from eg
                raise
        except Exception as e:
            # For other errors, log and retry if it's a connection-related error
            error_type = type(e).__name__
            error_str = str(e)
            print(f"❌ Error connecting to MCP server: {error_type}: {error_str}")
            
            # Check for authentication errors first - don't retry these
            auth_keywords = ['401', '403', 'unauthorized', 'forbidden', 'authentication']
            if any(keyword in error_str.lower() for keyword in auth_keywords):
                auth_msg = "MCP server requires authentication (OAuth or auth header). "
                if not config.oauth_provider and not config.auth_header:
                    auth_msg += "Please configure OAuth or provide an auth header."
                else:
                    auth_msg += "Authentication may have failed or expired."
                print(f"🔐 {auth_msg}")
                raise RuntimeError(auth_msg) from e
            
            # Retry on connection errors, but not on authentication errors
            retryable_keywords = ['connection', 'timeout', 'network', 'unreachable', 'refused', '500', '502', '503', '504']
            is_retryable = any(keyword in error_str.lower() for keyword in retryable_keywords)
            
            if attempt < max_retries - 1 and is_retryable:
                print(f"⚠️  Retrying in {retry_delay * (attempt + 1):.1f}s...")
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                # Don't retry on other non-retryable errors
                raise
    
    # Add web search tools if available
    web_tools = []
    try:
        # Try to add DuckDuckGo search (no API key required)
        from langchain_community.tools import DuckDuckGoSearchRun
        web_tools.append(DuckDuckGoSearchRun())
        print("✓ Added DuckDuckGo web search tool")
    except ImportError:
        pass  # DuckDuckGo not installed
    except Exception as e:
        print(f"⚠️  Could not add DuckDuckGo: {e}")
    
    try:
        # Try to add Tavily search (requires TAVILY_API_KEY)
        if os.environ.get("TAVILY_API_KEY"):
            from langchain_community.tools.tavily_search import TavilySearchResults
            tavily_tool = TavilySearchResults(max_results=3)
            web_tools.append(tavily_tool)
            print("✓ Added Tavily web search tool")
    except ImportError:
        pass  # Tavily not installed
    except Exception as e:
        print(f"⚠️  Could not add Tavily: {e}")
    
    # Combine MCP tools with web tools
    all_tools = list(tools) + web_tools
    
    if not all_tools:
        print("⚠️  No tools found on MCP server or available web tools")
    else:
        print(f"✓ Loaded {len(tools)} tool(s) from MCP server")
        if web_tools:
            print(f"✓ Added {len(web_tools)} web search tool(s)")
        for tool in tools:
            desc = tool.description or ""
            if len(desc) > 60:
                desc = desc[:60] + "..."
            print(f"  • {tool.name}: {desc}")

    # Get model string and create agent using create_agent
    model_string = get_model_string(config.provider, config.model)
    agent = create_agent(model_string, all_tools)
    
    print()
    
    # Call the ready callback with agent, client, and tools
    await on_ready(agent, client, tools)
