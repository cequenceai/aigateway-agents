"""MCP server configuration for Claude Agent SDK."""

import logging
from typing import Dict, Any, Optional

from mcp.client.auth import OAuthClientProvider, TokenStorage

logger = logging.getLogger(__name__)


async def build_mcp_server_config(
    mcp_url: str,
    auth_header: Optional[str] = None,
    oauth_provider: Optional[OAuthClientProvider] = None,
    storage: Optional[TokenStorage] = None,
    server_name: str = "mcp_server",
) -> Dict[str, Dict[str, Any]]:
    """
    Build MCP server configuration for Claude Agent SDK.
    
    The Claude Agent SDK expects MCP servers in this format:
    {
        "server_name": {
            "type": "http",
            "url": "https://server.com/mcp",
            "headers": {
                "Authorization": "Bearer <token>",
                "Accept": "application/json, text/event-stream"
            }
        }
    }
    
    Args:
        mcp_url: MCP server URL (e.g., https://server.com/mcp)
        auth_header: Optional static authorization header (e.g., "Bearer token")
        oauth_provider: Optional OAuth provider (will trigger OAuth if tokens missing)
        storage: Optional token storage to get tokens from
        server_name: Name for the MCP server in config
        
    Returns:
        Dictionary in Claude Agent SDK mcpServers format
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
            # This is necessary because Claude Agent SDK only accepts static headers
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
    
    # Build server config
    # The server requires Accept header with both content types
    headers = {
        "Accept": "application/json, text/event-stream"
    }
    
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
        logger.info("✓ MCP server configured with authentication")
    else:
        logger.warning("⚠ MCP server configured without authentication (may fail)")
    
    server_config: Dict[str, Any] = {
        "type": "http",
        "url": mcp_url,
        "headers": headers,
    }
    
    return {server_name: server_config}
