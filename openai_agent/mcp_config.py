"""MCP server configuration for OpenAI Agents SDK."""

import logging
from typing import Optional

from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from mcp.client.auth import OAuthClientProvider, TokenStorage

logger = logging.getLogger(__name__)


async def build_mcp_server(
    mcp_url: str,
    auth_header: Optional[str] = None,
    oauth_provider: Optional[OAuthClientProvider] = None,
    storage: Optional[TokenStorage] = None,
) -> MCPServerStreamableHttp:
    """
    Build MCP server instance for OpenAI Agents SDK.
    
    The OpenAI Agents SDK uses MCPServerStreamableHttp class instead of dict config.
    This function handles OAuth flow and creates the server instance with proper headers.
    
    Args:
        mcp_url: MCP server URL (e.g., https://server.com/mcp)
        auth_header: Optional static authorization header (e.g., "Bearer token")
        oauth_provider: Optional OAuth provider (will trigger OAuth if tokens missing)
        storage: Optional token storage to get tokens from
        
    Returns:
        MCPServerStreamableHttp instance configured for the server
    """
    # Get authorization token
    auth_token = None
    
    if auth_header:
        # Static auth header provided
        if auth_header.startswith("Bearer "):
            auth_token = auth_header[7:]  # Remove "Bearer " prefix
        else:
            auth_token = auth_header
        logger.info("✓ Using static auth header")
    elif storage:
        # Get token from storage
        try:
            tokens = await storage.get_tokens()
            if tokens and tokens.access_token:
                auth_token = tokens.access_token
                logger.info("✓ Loaded token from storage")
        except Exception as e:
            logger.debug(f"Could not load tokens from storage: {e}")
    
    # If no token found and we have oauth_provider, trigger OAuth registration
    if not auth_token and oauth_provider:
        try:
            # Use langchain-mcp-adapters to trigger OAuth registration
            # This is necessary because OpenAI Agents SDK only accepts static headers
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            logger.info("⚠ No token found - triggering OAuth registration...")
            
            mcp_config = {
                "mcp_server": {
                    "transport": "http",
                    "url": mcp_url,
                    "auth": oauth_provider,  # This triggers OAuth registration
                }
            }
            
            # Trigger OAuth by connecting - this will register the client and get tokens
            client = MultiServerMCPClient(mcp_config)
            await client.get_tools()  # This triggers OAuth registration and flow
            
            # Now get the token from storage
            if storage:
                tokens = await storage.get_tokens()
                if tokens and tokens.access_token:
                    auth_token = tokens.access_token
                    logger.info("✓ OAuth registration successful - token obtained")
            
            # Clean up client
            try:
                await client.close()
            except:
                pass
                
        except ImportError:
            logger.warning("⚠ langchain-mcp-adapters not available - cannot trigger OAuth automatically")
            logger.warning("   Install it with: pip install langchain-mcp-adapters")
        except Exception as e:
            logger.warning(f"⚠ Error triggering OAuth: {type(e).__name__}: {str(e)[:200]}")
    
    # Build headers for MCP server
    headers = {
        "Accept": "application/json, text/event-stream"
    }
    
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
        logger.info("✓ MCP server configured with authentication")
    else:
        logger.warning("⚠ MCP server configured without authentication (may fail)")
    
    # Create MCPServerStreamableHttpParams
    # MCPServerStreamableHttpParams is a TypedDict - create as dict with proper typing
    params = MCPServerStreamableHttpParams(
        url=mcp_url,
        headers=headers,
        timeout=120.0,  # 2 minute timeout in seconds
    )
    
    # Create MCPServerStreamableHttp instance for OpenAI Agents SDK
    mcp_server = MCPServerStreamableHttp(
        params=params,
        name="mcp_server",
        cache_tools_list=True,  # Cache tools list to reduce API calls
        max_retry_attempts=3,  # Retry failed requests
    )
    
    return mcp_server
