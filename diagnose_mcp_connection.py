#!/usr/bin/env python3
"""
MCP Connection Diagnostic Tool

This tool helps diagnose why one agent works but another doesn't by:
1. Testing the MCP server connection directly
2. Comparing how Claude agent vs Langchain agent connect
3. Identifying authentication issues
4. Checking OAuth token availability
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

console = Console()


async def test_direct_http_connection(mcp_url: str, auth_header: Optional[str] = None) -> Dict[str, Any]:
    """Test direct HTTP connection to MCP server."""
    import httpx
    
    result = {
        "success": False,
        "status_code": None,
        "error": None,
        "response_time": None,
        "headers": {}
    }
    
    headers = {
        "Accept": "application/json, text/event-stream"
    }
    
    if auth_header:
        headers["Authorization"] = auth_header
    
    try:
        start_time = asyncio.get_event_loop().time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(mcp_url, headers=headers)
            elapsed = asyncio.get_event_loop().time() - start_time
            
            result["success"] = response.status_code < 400
            result["status_code"] = response.status_code
            result["response_time"] = elapsed
            result["headers"] = dict(response.headers)
            
            if response.status_code == 401:
                result["error"] = "Unauthorized - Authentication required"
            elif response.status_code == 403:
                result["error"] = "Forbidden - Authentication failed or insufficient permissions"
            elif response.status_code >= 400:
                result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"
    except httpx.TimeoutException:
        result["error"] = "Connection timeout - Server may be unresponsive"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)}"
    
    return result


async def test_claude_agent_approach(mcp_url: str, auth_header: Optional[str] = None) -> Dict[str, Any]:
    """Test how Claude agent connects (pre-handles OAuth, uses static headers)."""
    result = {
        "success": False,
        "steps": [],
        "error": None,
        "token_available": False
    }
    
    try:
        # Import Claude agent's mcp_config
        anthropic_path = os.path.join(os.path.dirname(__file__), "anthropic_agent")
        sys.path.insert(0, anthropic_path)
        try:
            from mcp_config import build_mcp_server_config
            from oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage
        finally:
            sys.path.remove(anthropic_path)
        
        # Step 1: Check token storage
        result["steps"].append("Checking token storage...")
        storage = InMemoryTokenStorage()
        try:
            tokens = await storage.get_tokens()
            if tokens and tokens.access_token:
                result["token_available"] = True
                result["steps"].append(f"✓ Token found in storage (length: {len(tokens.access_token)})")
            else:
                result["steps"].append("⚠ No token in storage")
        except Exception as e:
            result["steps"].append(f"⚠ Could not check storage: {e}")
        
        # Step 2: Set up OAuth
        result["steps"].append("Setting up OAuth provider...")
        base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
        callback_server = CallbackServer(port=3030)
        callback_server.start()
        oauth_provider = create_oauth_provider(base_url, callback_server)
        result["steps"].append("✓ OAuth provider created")
        
        # Step 3: Build MCP config (this triggers OAuth if needed)
        result["steps"].append("Building MCP server config...")
        mcp_servers = await build_mcp_server_config(
            mcp_url=mcp_url,
            auth_header=auth_header,
            oauth_provider=oauth_provider,
            storage=storage,
            server_name="mcp_server"
        )
        result["steps"].append("✓ MCP config built")
        
        # Step 4: Check if auth token is in config
        if "mcp_server" in mcp_servers:
            server_config = mcp_servers["mcp_server"]
            if "headers" in server_config and "Authorization" in server_config["headers"]:
                result["success"] = True
                result["steps"].append("✓ Authorization header present in config")
            else:
                result["error"] = "No Authorization header in config"
                result["steps"].append("❌ No Authorization header in config")
        
        # Cleanup
        try:
            callback_server.stop()
        except:
            pass
            
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)}"
        result["steps"].append(f"❌ Error: {result['error']}")
    
    return result


async def test_langchain_agent_approach(mcp_url: str, auth_header: Optional[str] = None) -> Dict[str, Any]:
    """Test how Langchain agent connects (uses MultiServerMCPClient directly)."""
    result = {
        "success": False,
        "steps": [],
        "error": None,
        "exception_type": None
    }
    
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        
        # Step 1: Build config
        result["steps"].append("Building MultiServerMCPClient config...")
        mcp_config = {
            "mcp_server": {
                "transport": "http",
                "url": mcp_url,
            }
        }
        
        if auth_header:
            mcp_config["mcp_server"]["headers"] = {
                "Authorization": auth_header
            }
            result["steps"].append("✓ Static auth header added")
        else:
            result["steps"].append("⚠ No auth header provided")
        
        # Step 2: Create client
        result["steps"].append("Creating MultiServerMCPClient...")
        client = MultiServerMCPClient(mcp_config)
        result["steps"].append("✓ Client created")
        
        # Step 3: Try to get tools (this is where it fails)
        result["steps"].append("Calling get_tools()...")
        try:
            tools = await asyncio.wait_for(client.get_tools(), timeout=10.0)
            result["success"] = True
            result["steps"].append(f"✓ Successfully got {len(tools)} tools")
        except ExceptionGroup as eg:
            result["exception_type"] = "ExceptionGroup"
            error_details = []
            for exc in eg.exceptions:
                error_details.append(f"{type(exc).__name__}: {str(exc)}")
            result["error"] = "; ".join(error_details)
            result["steps"].append(f"❌ ExceptionGroup: {result['error']}")
        except asyncio.TimeoutError:
            result["exception_type"] = "TimeoutError"
            result["error"] = "Connection timed out after 10 seconds"
            result["steps"].append(f"❌ {result['error']}")
        except Exception as e:
            result["exception_type"] = type(e).__name__
            result["error"] = str(e)
            result["steps"].append(f"❌ {result['exception_type']}: {result['error']}")
        
        # Cleanup
        try:
            await client.close()
        except:
            pass
            
    except ImportError as e:
        result["error"] = f"Import error: {e}"
        result["steps"].append(f"❌ Could not import MultiServerMCPClient")
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)}"
        result["steps"].append(f"❌ Error: {result['error']}")
    
    return result


async def check_oauth_tokens() -> Dict[str, Any]:
    """Check if OAuth tokens exist in storage."""
    result = {
        "tokens_found": False,
        "token_path": None,
        "token_info": None
    }
    
    try:
        # Check common token storage locations
        token_paths = [
            Path.home() / ".mcp" / "tokens.json",
            Path.home() / ".config" / "mcp" / "tokens.json",
            Path.cwd() / ".mcp_tokens.json",
        ]
        
        for token_path in token_paths:
            if token_path.exists():
                result["tokens_found"] = True
                result["token_path"] = str(token_path)
                try:
                    with open(token_path, 'r') as f:
                        token_data = json.load(f)
                        result["token_info"] = {
                            "keys": list(token_data.keys()) if isinstance(token_data, dict) else "unknown",
                            "size": len(str(token_data))
                        }
                except:
                    result["token_info"] = "Could not read token file"
                break
    except Exception as e:
        result["error"] = str(e)
    
    return result


async def main():
    """Run diagnostics."""
    console.print(Panel.fit(
        "[bold cyan]MCP Connection Diagnostic Tool[/bold cyan]\n"
        "Comparing Claude Agent vs Langchain Agent connection methods",
        border_style="cyan"
    ))
    console.print()
    
    # Get MCP URL
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        mcp_url = console.input("[bold]Enter MCP server URL:[/bold] ").strip()
        if not mcp_url:
            console.print("[red]❌ MCP URL required[/red]")
            return
    
    auth_header = os.environ.get("MCP_AUTH_HEADER")
    if not auth_header:
        auth_input = console.input("[bold]Enter auth header (or press Enter to skip):[/bold] ").strip()
        auth_header = auth_input if auth_input else None
    
    console.print()
    console.print("[bold]Running diagnostics...[/bold]\n")
    
    # Test 1: Direct HTTP connection
    console.print("[cyan]1. Testing Direct HTTP Connection[/cyan]")
    http_result = await test_direct_http_connection(mcp_url, auth_header)
    if http_result["success"]:
        console.print(f"  ✅ Success (Status: {http_result['status_code']}, Time: {http_result['response_time']:.2f}s)")
    else:
        console.print(f"  ❌ Failed: {http_result['error']}")
        if http_result["status_code"]:
            console.print(f"     Status Code: {http_result['status_code']}")
    console.print()
    
    # Test 2: Check OAuth tokens
    console.print("[cyan]2. Checking OAuth Token Storage[/cyan]")
    token_result = await check_oauth_tokens()
    if token_result["tokens_found"]:
        console.print(f"  ✅ Tokens found at: {token_result['token_path']}")
        if token_result.get("token_info"):
            console.print(f"     Info: {token_result['token_info']}")
    else:
        console.print("  ⚠ No tokens found in common storage locations")
    console.print()
    
    # Test 3: Claude Agent approach
    console.print("[cyan]3. Testing Claude Agent Approach[/cyan]")
    claude_result = await test_claude_agent_approach(mcp_url, auth_header)
    for step in claude_result["steps"]:
        console.print(f"  {step}")
    if claude_result["success"]:
        console.print("  [green]✅ Claude Agent approach works![/green]")
    else:
        console.print(f"  [red]❌ Claude Agent approach failed: {claude_result.get('error', 'Unknown error')}[/red]")
    console.print()
    
    # Test 4: Langchain Agent approach
    console.print("[cyan]4. Testing Langchain Agent Approach[/cyan]")
    langchain_result = await test_langchain_agent_approach(mcp_url, auth_header)
    for step in langchain_result["steps"]:
        console.print(f"  {step}")
    if langchain_result["success"]:
        console.print("  [green]✅ Langchain Agent approach works![/green]")
    else:
        console.print(f"  [red]❌ Langchain Agent approach failed: {langchain_result.get('error', 'Unknown error')}[/red]")
        if langchain_result.get("exception_type"):
            console.print(f"     Exception Type: {langchain_result['exception_type']}")
    console.print()
    
    # Summary
    console.print(Panel.fit(
        "[bold]Summary[/bold]\n\n"
        f"Direct HTTP: {'✅' if http_result['success'] else '❌'} {http_result.get('error', 'OK')}\n"
        f"OAuth Tokens: {'✅' if token_result['tokens_found'] else '⚠'} {'Found' if token_result['tokens_found'] else 'Not found'}\n"
        f"Claude Agent: {'✅' if claude_result['success'] else '❌'} {'Works' if claude_result['success'] else claude_result.get('error', 'Failed')}\n"
        f"Langchain Agent: {'✅' if langchain_result['success'] else '❌'} {'Works' if langchain_result['success'] else langchain_result.get('error', 'Failed')}",
        border_style="yellow"
    ))
    
    # Recommendations
    console.print()
    console.print("[bold yellow]Recommendations:[/bold yellow]")
    
    if not http_result["success"] and http_result.get("status_code") == 401:
        console.print("  • MCP server requires authentication")
        console.print("  • Claude agent works because it pre-handles OAuth and gets tokens")
        console.print("  • Langchain agent fails because MultiServerMCPClient needs OAuth configured")
        console.print("  • Solution: Ensure OAuth provider is passed to Langchain agent config")
    
    if claude_result["success"] and not langchain_result["success"]:
        console.print("  • Claude agent succeeds because it:")
        console.print("    1. Checks token storage first")
        console.print("    2. Triggers OAuth if needed (using MultiServerMCPClient)")
        console.print("    3. Gets token from storage after OAuth")
        console.print("    4. Uses static headers with token")
        console.print("  • Langchain agent fails because:")
        console.print("    1. It relies on MultiServerMCPClient to handle OAuth during get_tools()")
        console.print("    2. If OAuth isn't configured or fails, it gets 401")
        console.print("  • Fix: Ensure OAuth provider is properly configured in Langchain agent")
    
    if token_result["tokens_found"] and not langchain_result["success"]:
        console.print("  • Tokens exist but Langchain agent can't use them")
        console.print("  • MultiServerMCPClient may not be reading from the same storage location")
        console.print("  • Check token storage path configuration")


if __name__ == "__main__":
    asyncio.run(main())
