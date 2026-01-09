#!/usr/bin/env python3
"""
Diagnostic script to investigate the 5.0 second ClientRequest timeout.

This script will:
1. Test the httpx_client_factory parameter
2. Trace where the 5.0 second timeout is coming from
3. Verify if our custom timeout is being used
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from openai_agent.mcp_config import build_mcp_server
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

# Enable httpx and MCP logging
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)

mcp_logger = logging.getLogger("agents.mcp")
mcp_logger.setLevel(logging.DEBUG)

mcp_client_logger = logging.getLogger("mcp.client")
mcp_client_logger.setLevel(logging.DEBUG)


async def test_connect():
    """Test mcp_server.connect() and trace where timeout occurs."""
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp")
    
    print("=" * 80)
    print("DIAGNOSING 5.0 SECOND CLIENTREQUEST TIMEOUT")
    print("=" * 80)
    print(f"MCP URL: {mcp_url}")
    print()
    
    # Import OAuth components
    from openai_agent.auth.oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage
    
    print("Step 1: Setting up OAuth...")
    storage = InMemoryTokenStorage()
    callback_server = CallbackServer(port=3032)
    callback_server.start()
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    oauth_provider = create_oauth_provider(base_url, callback_server)
    print("✓ OAuth setup complete")
    print()
    
    print("Step 2: Building MCP server with custom httpx_client_factory...")
    try:
        mcp_server = await build_mcp_server(
            mcp_url=mcp_url,
            oauth_provider=oauth_provider,
            storage=storage
        )
        print("✓ MCP server built")
        print()
        
        # Check if httpx_client_factory was set
        if hasattr(mcp_server, '_params'):
            params = mcp_server._params
            print(f"Params timeout: {params.get('timeout', 'N/A')}")
            print(f"httpx_client_factory set: {'httpx_client_factory' in params}")
            if 'httpx_client_factory' in params:
                print(f"  Factory type: {type(params['httpx_client_factory'])}")
        print()
        
        print("Step 3: Calling mcp_server.connect()...")
        print("   This is where the 5.0 second timeout likely occurs")
        print("   Watch for httpx DEBUG logs showing the actual timeout being used")
        print()
        
        try:
            await asyncio.wait_for(
                mcp_server.connect(),
                timeout=60.0  # 1 minute outer timeout
            )
            print("✓ Connection successful!")
        except Exception as e:
            print(f"❌ Connection failed: {type(e).__name__}: {e}")
            import traceback
            print("\nFull traceback:")
            print(traceback.format_exc())
            
            # Check for 5.0 second timeout
            error_str = str(e)
            if "5.0" in error_str or "ClientRequest" in error_str:
                print("\n" + "=" * 80)
                print("DIAGNOSIS: 5.0 SECOND TIMEOUT DETECTED")
                print("=" * 80)
                print("The error indicates a default 5.0 second httpx timeout is being used.")
                print("This suggests:")
                print("  1. The httpx_client_factory may not be called by the SDK")
                print("  2. The SDK might create its own httpx client with default timeout")
                print("  3. The connect() method might make a request before factory is used")
                print("\nCheck the httpx DEBUG logs above to see what timeout was actually used.")
    finally:
        callback_server.stop()


if __name__ == "__main__":
    asyncio.run(test_connect())
