"""MCP server configuration for OpenAI Agents SDK."""

import logging
import os
from typing import Optional, Callable

import httpx
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from mcp.client.auth import OAuthClientProvider, TokenStorage

# CRITICAL FIX: The 5.0 second timeout is httpx's default
# We need to ensure our factory is used, but also set a global fallback
# Set environment variable as hint (though httpx doesn't use it directly)
os.environ.setdefault("HTTPX_DEFAULT_READ_TIMEOUT", "300.0")

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
        # Get token from storage FIRST - this is the primary source
        try:
            tokens = await storage.get_tokens()
            if tokens and tokens.access_token:
                auth_token = tokens.access_token
                logger.info(f"✓ Loaded token from storage (length: {len(auth_token)})")
            else:
                logger.info("⚠ No token found in storage")
        except Exception as e:
            logger.debug(f"Could not load tokens from storage: {e}")
    
    # ONLY trigger OAuth if we have NO token AND have oauth_provider
    # Since we already checked storage above, we should have the token if it exists
    if not auth_token and oauth_provider:
        logger.info("⚠ No auth token found - will trigger OAuth registration")
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
            import asyncio
            logger.info("🔧 Creating MultiServerMCPClient for OAuth registration...")
            client = MultiServerMCPClient(mcp_config)
            logger.info("⏳ Calling client.get_tools() to trigger OAuth (timeout: 30s)...")
            # Use shorter timeout - OAuth should be quick if browser opens
            try:
                await asyncio.wait_for(client.get_tools(), timeout=30.0)  # 30 second timeout for OAuth
                logger.info("✓ OAuth registration successful")
                # Get token after successful OAuth
                if storage:
                    tokens = await storage.get_tokens()
                    if tokens and tokens.access_token:
                        auth_token = tokens.access_token
                        logger.info("✓ Token obtained after OAuth")
            except asyncio.TimeoutError:
                logger.warning("⚠ OAuth get_tools() timed out after 30s")
                # Don't fail - check if tokens were created
                if storage:
                    tokens = await storage.get_tokens()
                    if tokens and tokens.access_token:
                        auth_token = tokens.access_token
                        logger.info("✓ Token found after timeout - OAuth may have completed")
                    else:
                        logger.warning("⚠ No token found - OAuth may not have completed")
            except Exception as oauth_error:
                logger.warning(f"⚠ OAuth registration error: {type(oauth_error).__name__}: {str(oauth_error)[:200]}")
                # Check if tokens exist anyway (might have been created before error)
                if storage:
                    tokens = await storage.get_tokens()
                    if tokens and tokens.access_token:
                        auth_token = tokens.access_token
                        logger.info("✓ Token found despite error - using existing token")
            
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
    else:
        if auth_token:
            logger.info("✓ Token already loaded - skipping OAuth registration")
    
    # Build headers for MCP server
    headers = {
        "Accept": "application/json, text/event-stream"
    }
    
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
        logger.info("✓ MCP server configured with authentication")
    else:
        logger.warning("⚠ MCP server configured without authentication (may fail)")
    
    # Create custom httpx client factory with longer timeouts
    # The default 5.0 second timeout causes "ClientRequest" timeout errors
    # DIAGNOSIS: The error "Timed out while waiting for response to ClientRequest. Waited 5.0 seconds"
    # suggests that either:
    # 1. The httpx_client_factory parameter isn't being recognized/used
    # 2. There's a default httpx client being created elsewhere with 5.0s timeout
    # 3. The connect() method makes a request before our custom client is used
    
    # Track if factory is called (for debugging)
    factory_called = {"called": False, "count": 0}
    
    def create_httpx_client(**kwargs) -> httpx.AsyncClient:
        """
        Create httpx client with extended timeouts for MCP server.
        
        The SDK calls this factory with: headers, timeout, auth
        We accept all kwargs and override timeout for slow MCP servers.
        """
        # Track that factory was called
        factory_called["called"] = True
        factory_called["count"] += 1
        
        logger.info(f"🔧 [FACTORY CALL #{factory_called['count']}] Creating custom httpx client...")
        logger.info(f"   SDK passed kwargs: {list(kwargs.keys())}")
        
        # Override timeout with our extended values
        # The SDK passes a default timeout, but we want longer for slow servers
        custom_timeout = httpx.Timeout(
            connect=30.0,   # 30 seconds to establish connection
            read=300.0,     # 5 minutes to read response (for slow MCP servers)
            write=30.0,     # 30 seconds to write request
            pool=30.0,      # 30 seconds for connection pooling
        )
        
        sdk_timeout = kwargs.pop('timeout', None)
        logger.info(f"   SDK requested timeout: {sdk_timeout}")
        logger.info(f"   Using custom timeout: connect=30s, read=300s")
        
        # Create client with our custom timeout, passing through all other kwargs
        client = httpx.AsyncClient(
            timeout=custom_timeout,
            **kwargs
        )
        
        logger.info(f"✓ [FACTORY CALL #{factory_called['count']}] Custom httpx client created with 300s read timeout")
        
        return client
    
    # Create MCPServerStreamableHttpParams
    # MCPServerStreamableHttpParams is a TypedDict - create as dict with proper typing
    # Increased timeout significantly to handle slow MCP server responses
    # DIAGNOSIS: The 5.0 second timeout suggests httpx default is being used somewhere
    # We're setting both timeout (for SDK) and httpx_client_factory (for underlying HTTP client)
    logger.info("🔧 Creating MCPServerStreamableHttpParams with extended timeouts...")
    logger.info(f"   - timeout: 300.0 seconds")
    logger.info(f"   - httpx_client_factory: custom client with 300s read timeout")
    
    params = MCPServerStreamableHttpParams(
        url=mcp_url,
        headers=headers,
        timeout=300.0,  # 5 minute timeout in seconds (increased to handle slow responses and OAuth flows)
        httpx_client_factory=create_httpx_client,  # Use custom httpx client with longer timeouts
    )
    logger.info("✓ MCPServerStreamableHttpParams created successfully")
    
    # Verify params before creating server
    logger.info("🔍 Verifying params before creating MCPServerStreamableHttp...")
    logger.info(f"   - url: {params.get('url', 'N/A')}")
    logger.info(f"   - timeout: {params.get('timeout', 'N/A')}")
    logger.info(f"   - httpx_client_factory: {params.get('httpx_client_factory', 'N/A')}")
    if 'httpx_client_factory' in params and params['httpx_client_factory']:
        logger.info(f"   - httpx_client_factory type: {type(params['httpx_client_factory'])}")
        logger.info(f"   - httpx_client_factory callable: {callable(params['httpx_client_factory'])}")
    
    # Create MCPServerStreamableHttp instance for OpenAI Agents SDK
    logger.info("🔧 Creating MCPServerStreamableHttp instance...")
    mcp_server = MCPServerStreamableHttp(
        params=params,
        name="mcp_server",
        cache_tools_list=True,  # Cache tools list to reduce API calls
        max_retry_attempts=3,  # Retry failed requests
    )
    logger.info("✓ MCPServerStreamableHttp created")
    
    # Try to verify the httpx client factory is accessible
    if hasattr(mcp_server, '_params'):
        stored_params = mcp_server._params
        if 'httpx_client_factory' in stored_params:
            logger.info("✓ httpx_client_factory is stored in server params")
            logger.info(f"   Factory will be called when SDK needs an httpx client")
            logger.info(f"   If you see 'FACTORY CALL #' logs, the factory is being used")
            logger.info(f"   If you DON'T see those logs but get 5.0s timeout, factory is NOT being called")
        else:
            logger.warning("⚠ httpx_client_factory NOT found in server params - may not be used!")
            logger.warning("   This could explain why 5.0s default timeout is used")
    else:
        logger.warning("⚠ Cannot verify params - mcp_server doesn't have _params attribute")
    
    return mcp_server
