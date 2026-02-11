#!/usr/bin/env python3
"""
OpenAI Agent - Interactive terminal agent using OpenAI Agents SDK.

Usage:
    python agent.py --mcp-url https://server.com/mcp
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from agents import Runner
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent.graph import AgentConfig, run_agent_session
from auth.oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

console = Console()


def print_banner() -> None:
    """Print the application banner."""
    console.print()
    console.print("╔══════════════════════════════════════════════════╗", style="bold green")
    console.print("║  🤖 OpenAI Agent - Interactive Chat             ║", style="bold green")
    console.print("╚══════════════════════════════════════════════════╝", style="bold green")
    console.print()


def check_api_key() -> bool:
    """Check if API key is set."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]Error: OPENAI_API_KEY environment variable not set.[/red]")
        console.print("[yellow]Please set it with: export OPENAI_API_KEY='your-key'[/yellow]")
        return False
    return True


async def chat_loop(agent, mcp_server):
    """Run the interactive chat loop."""
    console.print(
        "[dim]Type your message and press Enter. Use Ctrl+C or /quit to exit.[/dim]\n"
    )

    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ")
            
            if not user_input.strip():
                continue
            
            # Handle special commands
            if user_input.lower() in ["/quit", "/exit", "/q"]:
                console.print("\n[dim]Goodbye! 👋[/dim]")
                break
            
            if user_input.lower() == "/clear":
                console.clear()
                print_banner()
                console.print("[dim]Conversation cleared.[/dim]\n")
                continue
            
            if user_input.lower() == "/help":
                console.print(Panel(
                    "[bold]/quit, /exit, /q[/bold] - Exit the chat\n"
                    "[bold]/clear[/bold] - Clear conversation history\n"
                    "[bold]/help[/bold] - Show this help message",
                    title="Commands",
                    border_style="green",
                ))
                continue
            
            console.print()
            console.print("[bold blue]Assistant:[/bold blue]")
            
            # Run agent with user input
            result = await Runner.run(agent, user_input)
            
            # Display the response as markdown
            if result.final_output:
                console.print(Markdown(result.final_output))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n\n[dim]Goodbye! 👋[/dim]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")
            import traceback
            traceback.print_exc()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="OpenAI Agent - Interactive chat using OpenAI Agents SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python agent.py --mcp-url https://server.com/mcp

  # With static auth header
  python agent.py --mcp-url https://server.com/mcp --auth-header "Bearer token"

  # Without OAuth
  python agent.py --mcp-url https://server.com/mcp --no-oauth
        """,
    )
    
    parser.add_argument(
        "--mcp-url",
        required=True,
        help="MCP server URL (e.g., https://server.com/mcp)",
    )
    
    parser.add_argument(
        "--auth-header",
        help="Static authorization header (e.g., 'Bearer token')",
    )
    
    parser.add_argument(
        "--no-oauth",
        action="store_true",
        help="Disable automatic OAuth flow",
    )
    
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="OpenAI model to use (default: gpt-4o)",
    )
    
    return parser.parse_args()


async def main_async() -> None:
    """Async main entry point."""
    args = parse_args()
    
    print_banner()
    
    if not check_api_key():
        sys.exit(1)
    
    console.print("[dim]✓ API key loaded[/dim]\n")
    
    # Determine base URL (remove /mcp suffix for OAuth)
    base_url = args.mcp_url
    if base_url.endswith("/mcp"):
        base_url = base_url[:-4]
    
    # Set up authentication
    oauth_provider = None
    callback_server = None
    storage = None
    
    if not args.auth_header and not args.no_oauth:
        console.print("[dim]Setting up OAuth authentication...[/dim]")
        storage = InMemoryTokenStorage(reset_tokens=False)
        callback_server = CallbackServer(port=3030)
        callback_server.start()
        oauth_provider = create_oauth_provider(base_url, callback_server, reset_tokens=False)
        
        # Check if we need to authenticate
        tokens = await storage.get_tokens()
        if not tokens or not tokens.access_token:
            console.print("[yellow]⚠ No existing tokens found - OAuth will be triggered automatically[/yellow]")
            console.print("[dim]The browser will open when OAuth is needed...[/dim]\n")
    
    # Create agent configuration
    config = AgentConfig(
        mcp_url=args.mcp_url,
        model=args.model,
        auth_header=args.auth_header,
        oauth_provider=oauth_provider,
        storage=storage,
    )
    
    console.print(f"[dim]Using model: {args.model}[/dim]")
    console.print()
    
    try:
        async def on_agent_ready(agent, mcp_server):
            """Called when agent is ready."""
            console.print()
            await chat_loop(agent, mcp_server)
        
        # Run the agent session
        await run_agent_session(config, on_agent_ready)
        
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if callback_server:
            callback_server.stop()
            console.print("[dim]✓ Callback server stopped[/dim]")


def main() -> None:
    """Main entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
