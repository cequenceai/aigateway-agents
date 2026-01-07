#!/usr/bin/env python3
"""
Generic MCP integration test for OpenAI Agents SDK.

This test demonstrates connecting to any MCP server (Slack is used as an example).
"""

import argparse
import asyncio
import logging
import os
import sys

from agents import Agent, Runner
from rich.console import Console
from rich.panel import Panel

from mcp_config import build_mcp_server
from auth.oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

console = Console()


def print_banner():
    """Print test banner."""
    console.print()
    console.print("╔══════════════════════════════════════════════════╗", style="bold green")
    console.print("║  🧪 MCP Integration Test - OpenAI Agents SDK     ║", style="bold green")
    console.print("╚══════════════════════════════════════════════════╝", style="bold green")
    console.print()


async def test_mcp_connection(mcp_url: str, auth_header: str = None):
    """Test connection to MCP server."""
    print_banner()
    
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]Error: OPENAI_API_KEY not set[/red]")
        return False
    
    console.print(f"[dim]MCP Server URL:[/dim] {mcp_url}")
    console.print()
    
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    storage = InMemoryTokenStorage(reset_tokens=False)
    callback_server = CallbackServer(port=3030)
    callback_server.start()
    oauth_provider = create_oauth_provider(base_url, callback_server, reset_tokens=False)
    
    try:
        mcp_server = await build_mcp_server(
            mcp_url=mcp_url,
            auth_header=auth_header,
            oauth_provider=oauth_provider,
            storage=storage
        )
        
        await mcp_server.connect()
        console.print("[green]✓ Connected to MCP server[/green]")
        console.print()
        
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        
        agent = Agent(
            name="Test Agent",
            instructions="You are a helpful assistant with access to MCP server tools.",
            model=model,
            mcp_servers=[mcp_server]
        )
        
        # Test: List tools
        console.print(Panel(
            "[bold]Test:[/bold] Listing available tools from MCP server",
            border_style="green"
        ))
        
        result = await Runner.run(
            agent,
            "List all available tools from the MCP server and describe what each one does."
        )
        
        if result and result.final_output:
            console.print(result.final_output)
        
        console.print()
        console.print("[green]✅ MCP integration test completed![/green]")
        
        await mcp_server.cleanup()
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False
    finally:
        callback_server.stop()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test MCP server integration")
    parser.add_argument("--mcp-url", required=True, help="MCP server URL")
    parser.add_argument("--auth-header", help="Static auth header")
    args = parser.parse_args()
    
    success = await test_mcp_connection(
        mcp_url=args.mcp_url,
        auth_header=args.auth_header
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
