#!/usr/bin/env python3
"""
Generic MCP integration test for Claude Agent SDK.

This test demonstrates connecting to any MCP server (Slack is used as an example).
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions
from rich.console import Console
from rich.panel import Panel

from mcp_config import build_mcp_server_config
from oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

console = Console()


def print_banner():
    """Print test banner."""
    console.print()
    console.print("╔══════════════════════════════════════════════════╗", style="bold blue")
    console.print("║  🧪 MCP Integration Test - Claude Agent SDK     ║", style="bold blue")
    console.print("╚══════════════════════════════════════════════════╝", style="bold blue")
    console.print()


async def test_mcp_connection(mcp_url: str, auth_header: str = None, server_name: str = "mcp_server"):
    """Test connection to MCP server."""
    print_banner()
    
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        return False
    
    console.print(f"[dim]MCP Server URL:[/dim] {mcp_url}")
    console.print(f"[dim]Server Name:[/dim] {server_name}")
    console.print()
    
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    storage = InMemoryTokenStorage(reset_tokens=False)
    callback_server = CallbackServer(port=3030)
    callback_server.start()
    oauth_provider = create_oauth_provider(base_url, callback_server, reset_tokens=False)
    
    try:
        mcp_servers = await build_mcp_server_config(
            mcp_url=mcp_url,
            auth_header=auth_header,
            oauth_provider=oauth_provider,
            storage=storage,
            server_name=server_name
        )
        
        options = ClaudeAgentOptions(
            mcp_servers=mcp_servers,
            permission_mode="bypassPermissions",
            env={"ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY")}
        )
        
        # Test 1: List tools
        console.print(Panel(
            "[bold]Test 1:[/bold] Listing available tools from MCP server",
            border_style="green"
        ))
        
        async for message in query(
            prompt="List all available tools from the MCP server and describe what each one does.",
            options=options
        ):
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        console.print(block.text)
        
        console.print()
        console.print("[green]✅ MCP integration test completed![/green]")
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
    parser.add_argument("--server-name", default="mcp_server", help="Server name in config")
    args = parser.parse_args()
    
    success = await test_mcp_connection(
        mcp_url=args.mcp_url,
        auth_header=args.auth_header,
        server_name=args.server_name
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
