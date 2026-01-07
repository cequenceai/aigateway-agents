#!/usr/bin/env python3
"""
MCP Agent CLI - Interactive terminal agent connected to MCP servers.

Usage:
    python mcp_agent.py --mcp-url http://localhost:8000/mcp
    python mcp_agent.py --mcp-url http://localhost:8000/mcp --auth-header "Bearer token"
"""

import argparse
import asyncio
import os
import sys

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner

from .agent.graph import AgentConfig, run_agent_session
from .auth.oauth import CallbackServer, create_oauth_provider


console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Interactive MCP Agent - Chat with AI using MCP server tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (will auto-handle OAuth if server requires it)
  python mcp_agent.py --mcp-url http://localhost:8000/mcp

  # With static auth header
  python mcp_agent.py --mcp-url http://localhost:8000/mcp --auth-header "Bearer my-token"

Environment Variables:
  ANTHROPIC_API_KEY    API key for Anthropic (required if using Anthropic provider)
  OPENAI_API_KEY       API key for OpenAI (required if using OpenAI provider)
  MCP_AGENT_PROVIDER   Default LLM provider (anthropic or openai)
  MCP_AGENT_MODEL      Default LLM model
        """,
    )

    # Required arguments
    parser.add_argument(
        "--mcp-url",
        required=True,
        help="MCP server URL (e.g., http://localhost:8000/mcp)",
    )

    # Authentication options
    auth_group = parser.add_argument_group("Authentication")
    auth_group.add_argument(
        "--auth-header",
        help="Authorization header value (e.g., 'Bearer token123')",
    )
    auth_group.add_argument(
        "--no-oauth",
        action="store_true",
        help="Disable automatic OAuth flow",
    )

    # LLM options
    llm_group = parser.add_argument_group("LLM Configuration")
    llm_group.add_argument(
        "--provider",
        choices=["anthropic", "openai"],
        default=os.environ.get("MCP_AGENT_PROVIDER", "anthropic"),
        help="LLM provider (default: anthropic or MCP_AGENT_PROVIDER env var)",
    )
    llm_group.add_argument(
        "--model",
        default=os.environ.get("MCP_AGENT_MODEL"),
        help="LLM model name (default: provider-specific default or MCP_AGENT_MODEL env var)",
    )

    return parser.parse_args()


def print_banner() -> None:
    """Print the application banner."""
    console.print()
    console.print("╔══════════════════════════════════════════════════╗", style="bold blue")
    console.print("║  🤖 MCP Agent - Interactive Terminal Chat       ║", style="bold blue")
    console.print("╚══════════════════════════════════════════════════╝", style="bold blue")
    console.print()


def format_tool_call(tool_name: str, tool_args: dict) -> Panel:
    """Format a tool call for display."""
    args_str = "\n".join(f"  {k}: {v}" for k, v in tool_args.items())
    content = f"[bold cyan]{tool_name}[/bold cyan]\n{args_str}" if args_str else f"[bold cyan]{tool_name}[/bold cyan]"
    return Panel(content, title="🔧 Tool Call", border_style="cyan", expand=False)


def format_tool_result(result: str) -> Panel:
    """Format a tool result for display."""
    # Truncate very long results
    if len(result) > 500:
        result = result[:500] + "...[truncated]"
    return Panel(result, title="📋 Result", border_style="green", expand=False)


def display_agent_response(result: dict) -> str:
    """
    Display the agent response with tool calls and final answer.
    Returns the final text response.
    """
    messages = result.get("messages", [])
    final_response = ""
    
    for message in messages:
        if isinstance(message, AIMessage):
            # Check for tool calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    console.print(format_tool_call(
                        tool_call.get("name", "unknown"),
                        tool_call.get("args", {})
                    ))
            
            # Display text content if present
            if message.content:
                if isinstance(message.content, str):
                    final_response = message.content
                elif isinstance(message.content, list):
                    # Handle list of content blocks
                    text_parts = []
                    for block in message.content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    final_response = "".join(text_parts)
        
        elif isinstance(message, ToolMessage):
            # Display tool results
            content = message.content
            if isinstance(content, str):
                console.print(format_tool_result(content))
            else:
                console.print(format_tool_result(str(content)))
    
    # Display the final response as markdown
    if final_response:
        console.print(Markdown(final_response))
    
    return final_response


async def run_agent_query(agent, messages: list[dict]) -> dict:
    """Run the agent with the given messages and return the result."""
    with Live(Spinner("dots", text="Thinking..."), console=console, refresh_per_second=10):
        result = await agent.ainvoke({"messages": messages})
    return result


async def chat_loop(agent) -> None:
    """Run the interactive chat loop."""
    messages = []
    
    console.print(
        "[dim]Type your message and press Enter. Use Ctrl+C or /quit to exit.[/dim]\n"
    )

    while True:
        try:
            # Get user input
            user_input = console.input("[bold green]You:[/bold green] ")
            
            if not user_input.strip():
                continue
            
            # Handle special commands
            if user_input.lower() in ["/quit", "/exit", "/q"]:
                console.print("\n[dim]Goodbye! 👋[/dim]")
                break
            
            if user_input.lower() == "/clear":
                messages = []
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
                    border_style="blue",
                ))
                continue

            # Add user message to history
            messages.append({"role": "user", "content": user_input})
            
            console.print()
            console.print("[bold blue]Assistant:[/bold blue]")
            
            # Run agent and get response
            result = await run_agent_query(agent, messages)
            
            # Display the response (including tool calls)
            response = display_agent_response(result)
            
            # Add assistant response to history for context
            if response:
                messages.append({"role": "assistant", "content": response})
            
            console.print()

        except KeyboardInterrupt:
            console.print("\n\n[dim]Goodbye! 👋[/dim]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")
            import traceback
            traceback.print_exc()


async def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    print_banner()
    
    console.print(f"[dim]Connecting to MCP server: {args.mcp_url}[/dim]")
    
    # Determine base URL (remove /mcp suffix for OAuth)
    base_url = args.mcp_url
    if base_url.endswith("/mcp"):
        base_url = base_url[:-4]
    
    # Set up authentication
    oauth_provider = None
    callback_server = None
    
    if not args.auth_header and not args.no_oauth:
        # Set up OAuth flow
        callback_server = CallbackServer(port=3030)
        callback_server.start()
        oauth_provider = create_oauth_provider(base_url, callback_server)

    # Create agent configuration
    config = AgentConfig(
        mcp_url=args.mcp_url,
        provider=args.provider,
        model=args.model,
        auth_header=args.auth_header,
        oauth_provider=oauth_provider,
    )

    console.print(f"[dim]Using LLM: {args.provider}/{config.model}[/dim]")
    console.print()

    try:
        async def on_agent_ready(agent, client, tools):
            """Called when agent is ready."""
            console.print()
            await chat_loop(agent)

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


if __name__ == "__main__":
    asyncio.run(main())
