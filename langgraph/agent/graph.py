"""LangGraph agent with MCP tool integration using langchain-mcp-adapters."""

import asyncio
import os
import time as _time
from dataclasses import dataclass
from typing import Any

import httpx
from langchain_core.language_models import BaseChatModel
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.client.auth import OAuthClientProvider


def _elapsed_since(start: float) -> str:
    """Format elapsed time since start."""
    return f"{_time.time() - start:.3f}s"


async def _check_server_connectivity(
    mcp_url: str,
    session_start: float,
    timeout: float = 5.0,
) -> bool:
    """
    Perform a quick connectivity check to the MCP server.
    
    This helps isolate network issues from client-side issues.
    
    Args:
        mcp_url: The MCP server URL
        session_start: Session start time for logging
        timeout: Timeout for the check (default: 5s)
        
    Returns:
        True if server is reachable, False otherwise
    """
    # Try the base URL (remove /mcp suffix if present)
    base_url = mcp_url.rstrip("/")
    if base_url.endswith("/mcp"):
        base_url = base_url[:-4]
    
    # Try common health endpoints
    endpoints_to_try = [
        f"{base_url}/health",
        f"{base_url}/",
        mcp_url,  # Try the MCP endpoint itself
    ]
    
    print(f"[DEBUG T+{_elapsed_since(session_start)}] Checking server connectivity...")
    
    async with httpx.AsyncClient(timeout=timeout) as http_client:
        for endpoint in endpoints_to_try:
            try:
                check_start = _time.time()
                resp = await http_client.get(endpoint)
                check_elapsed = _time.time() - check_start
                print(f"[DEBUG T+{_elapsed_since(session_start)}] ✓ {endpoint} responded with {resp.status_code} in {check_elapsed:.3f}s")
                return True
            except httpx.TimeoutException:
                print(f"[DEBUG T+{_elapsed_since(session_start)}] ✗ {endpoint} timed out after {timeout}s")
            except httpx.ConnectError as e:
                print(f"[DEBUG T+{_elapsed_since(session_start)}] ✗ {endpoint} connection failed: {e}")
            except Exception as e:
                print(f"[DEBUG T+{_elapsed_since(session_start)}] ✗ {endpoint} error: {type(e).__name__}: {e}")
    
    print(f"[DEBUG T+{_elapsed_since(session_start)}] ⚠️  Server connectivity check failed for all endpoints")
    return False


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
    tools_timeout: float = 300.0,
    check_connectivity: bool = True,
    skip_tools: bool = False,
):
    """
    Run an agent session with the MCP server using MultiServerMCPClient.
    
    Args:
        config: Agent configuration
        on_ready: Callback function called with (agent, client, tools) when ready
        tools_timeout: Timeout in seconds for fetching tools (default: 300s / 5 min).
                      Note: This includes OAuth authentication time if the user needs
                      to authenticate in the browser, so it should be generous.
        check_connectivity: Whether to check server connectivity before connecting (default: True)
        skip_tools: If True, skip fetching tools and start with empty tools list (for debugging)
    """
    session_start = _time.time()
    
    # Optional: Check server connectivity first to isolate network issues
    if check_connectivity:
        is_reachable = await _check_server_connectivity(config.mcp_url, session_start)
        if not is_reachable:
            print(f"[DEBUG T+{_elapsed_since(session_start)}] ⚠️  Server may be unreachable, but continuing...")
    
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

    # Create the MultiServerMCPClient with timing
    print(f"[DEBUG T+{_elapsed_since(session_start)}] Creating MultiServerMCPClient...")
    print(f"[DEBUG] Config: transport={mcp_config['mcp_server']['transport']}, url={mcp_config['mcp_server']['url']}")
    print(f"[DEBUG] Has auth: {'auth' in mcp_config['mcp_server']}")
    print(f"[DEBUG] Has headers: {'headers' in mcp_config['mcp_server']}")
    
    tools = []
    client = None
    
    if skip_tools:
        # Skip normal flow - do OAuth first, then use token as header
        print(f"[DEBUG T+{_elapsed_since(session_start)}] skip_tools=True: OAuth first, then use token as Bearer header...")
        
        if config.oauth_provider:
            print(f"[DEBUG T+{_elapsed_since(session_start)}] Step 1: Complete OAuth to get tokens...")
            storage = config.oauth_provider.context.storage
            tokens = await storage.get_tokens()
            
            if not tokens:
                # Need to authenticate - trigger OAuth by making a request
                print(f"[DEBUG T+{_elapsed_since(session_start)}] No tokens yet, triggering OAuth flow...")
                
                # Create a temp client just to trigger OAuth
                temp_config = {"temp_server": {"transport": "http", "url": config.mcp_url, "auth": config.oauth_provider}}
                temp_client = MultiServerMCPClient(temp_config)
                
                # Wait for tokens to appear (OAuth callback will set them)
                async def wait_for_tokens():
                    while True:
                        t = await storage.get_tokens()
                        if t:
                            return t
                        await asyncio.sleep(0.5)
                
                # Start get_tools (triggers OAuth) and wait for tokens
                get_tools_task = asyncio.create_task(temp_client.get_tools())
                tokens_task = asyncio.create_task(wait_for_tokens())
                
                try:
                    tokens = await asyncio.wait_for(tokens_task, timeout=120)
                    print(f"[DEBUG T+{_elapsed_since(session_start)}] ✓ OAuth complete, got tokens!")
                    print(f"[DEBUG T+{_elapsed_since(session_start)}]   Cancelling hanging get_tools()...")
                    get_tools_task.cancel()
                    try:
                        await get_tools_task
                    except asyncio.CancelledError:
                        pass
                except asyncio.TimeoutError:
                    print(f"[DEBUG T+{_elapsed_since(session_start)}] ✗ Timeout waiting for OAuth")
                    raise
            
            # Step 2: Create NEW client with token as Bearer header (no OAuthProvider)
            print(f"[DEBUG T+{_elapsed_since(session_start)}] Step 2: Creating new MCP client with Bearer token header...")
            
            new_config = {
                "mcp_server": {
                    "transport": "http",
                    "url": config.mcp_url,
                    "headers": {
                        "Authorization": f"Bearer {tokens.access_token}"
                    }
                }
            }
            
            client = MultiServerMCPClient(new_config)
            print(f"[DEBUG T+{_elapsed_since(session_start)}] Step 3: Calling get_tools() with Bearer token...")
            
            get_tools_start = _time.time()
            try:
                async with asyncio.timeout(30):  # Shorter timeout now
                    tools = await client.get_tools()
                print(f"[DEBUG T+{_elapsed_since(session_start)}] ✓ get_tools() returned {len(tools) if tools else 0} tools in {_elapsed_since(get_tools_start)}")
            except asyncio.TimeoutError:
                print(f"[DEBUG T+{_elapsed_since(session_start)}] ✗ get_tools() still timed out with Bearer token!")
                print(f"[DEBUG T+{_elapsed_since(session_start)}]   This suggests the MCP server is not responding to initialize request.")
                tools = []
            except Exception as e:
                print(f"[DEBUG T+{_elapsed_since(session_start)}] ✗ get_tools() failed: {type(e).__name__}: {e}")
                tools = []
        else:
            print(f"[DEBUG T+{_elapsed_since(session_start)}] No OAuth provider, continuing with empty tools...")
    else:
        # Normal flow - create client and fetch tools
        client_create_start = _time.time()
        client = MultiServerMCPClient(mcp_config)
        print(f"[DEBUG T+{_elapsed_since(session_start)}] MultiServerMCPClient created in {_elapsed_since(client_create_start)}")
        
        # Get tools from MCP server with timeout
        print(f"[DEBUG T+{_elapsed_since(session_start)}] Calling client.get_tools() (timeout: {tools_timeout}s)...")
        get_tools_start = _time.time()
        
        # Background task to print progress every 5 seconds
        progress_task = None
        async def print_progress():
            while True:
                await asyncio.sleep(5)
                elapsed = _time.time() - get_tools_start
                print(f"   [DEBUG T+{_elapsed_since(session_start)}] ... still waiting for get_tools() ({elapsed:.1f}s elapsed)")
        
        try:
            progress_task = asyncio.create_task(print_progress())
            async with asyncio.timeout(tools_timeout):
                tools = await client.get_tools()
            print(f"[DEBUG T+{_elapsed_since(session_start)}] get_tools() returned {len(tools) if tools else 0} tools in {_elapsed_since(get_tools_start)}")
        except asyncio.TimeoutError:
            print(f"[DEBUG T+{_elapsed_since(session_start)}] ✗ get_tools() TIMED OUT after {tools_timeout}s")
            raise TimeoutError(f"Fetching tools from MCP server timed out after {tools_timeout}s. The server may be unresponsive.")
        except Exception as e:
            print(f"[DEBUG T+{_elapsed_since(session_start)}] ✗ get_tools() raised {type(e).__name__} after {_elapsed_since(get_tools_start)}: {e}")
            raise
        finally:
            if progress_task:
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass
        
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
    print(f"[DEBUG T+{_elapsed_since(session_start)}] Creating agent...")
    agent_create_start = _time.time()
    model_string = get_model_string(config.provider, config.model)
    agent = create_agent(model_string, tools)
    print(f"[DEBUG T+{_elapsed_since(session_start)}] Agent created in {_elapsed_since(agent_create_start)}")
    
    print(f"[DEBUG T+{_elapsed_since(session_start)}] Total setup time: {_elapsed_since(session_start)}")
    print()
    
    # Call the ready callback with agent, client, and tools
    await on_ready(agent, client, tools)
