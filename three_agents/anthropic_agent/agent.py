#!/usr/bin/env python3
"""
Anthropic Agent using Claude Agent SDK.

This agent uses the claude-agent-sdk to interact with Claude models.
It provides a simple interface for running queries with tool support.
"""

import asyncio
import os
import sys
from typing import Optional, List, Dict, Any

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


def print_banner() -> None:
    """Print the application banner."""
    console.print()
    console.print("╔══════════════════════════════════════════════════╗", style="bold blue")
    console.print("║  🤖 Claude Agent SDK - Interactive Chat        ║", style="bold blue")
    console.print("╚══════════════════════════════════════════════════╝", style="bold blue")
    console.print()


async def run_query(
    prompt: str,
    allowed_tools: Optional[List[str]] = None,
    system_prompt: Optional[str] = None,
    max_turns: int = 10,
    permission_mode: str = "acceptEdits",
    mcp_servers: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Run a query using the Claude Agent SDK.
    
    Args:
        prompt: The user's prompt/question
        allowed_tools: List of allowed tools (e.g., ["Read", "Edit", "Bash"])
        system_prompt: Optional system prompt
        max_turns: Maximum number of turns in the conversation
        permission_mode: Permission mode ("acceptEdits", "requireApproval", etc.)
        mcp_servers: Optional MCP server configuration
        
    Returns:
        The final response text
    """
    # Build options
    options_kwargs = {
        "permission_mode": permission_mode,
        "max_turns": max_turns,
    }
    
    if allowed_tools:
        options_kwargs["allowed_tools"] = allowed_tools
    
    if system_prompt:
        options_kwargs["system_prompt"] = system_prompt
    
    if mcp_servers:
        options_kwargs["mcp_servers"] = mcp_servers
    
    options = ClaudeAgentOptions(**options_kwargs)
    
    # Collect response
    response_text = ""
    tool_calls_shown = set()
    
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                # Display Claude's reasoning and tool calls
                if message.content:
                    for block in message.content:
                        if hasattr(block, "text") and block.text:
                            response_text += block.text + "\n"
                        elif hasattr(block, "name"):
                            # Tool being called
                            tool_name = block.name
                            if tool_name not in tool_calls_shown:
                                console.print(f"[dim]🔧 Using tool: {tool_name}[/dim]")
                                tool_calls_shown.add(tool_name)
            elif isinstance(message, ResultMessage):
                # Final result
                if message.subtype == "success":
                    if hasattr(message, "content") and message.content:
                        if isinstance(message.content, str):
                            response_text += message.content
                        elif isinstance(message.content, list):
                            for item in message.content:
                                if isinstance(item, str):
                                    response_text += item
                                elif hasattr(item, "text"):
                                    response_text += item.text
                elif message.subtype == "error":
                    if hasattr(message, "result"):
                        error_msg = str(message.result)
                        response_text += f"\nError: {error_msg}"
    except Exception as e:
        if response_text.strip():
            return response_text.strip()
        raise
    
    return response_text.strip()


async def interactive_chat() -> None:
    """Run an interactive chat loop."""
    console.print(
        "[dim]Type your message and press Enter. Use Ctrl+C or /quit to exit.[/dim]\n"
    )
    
    # Default tools
    default_tools = ["Read", "Edit", "Bash"]
    
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
                    "[bold]/help[/bold] - Show this help message\n"
                    "[bold]/tools[/bold] - Show available tools",
                    title="Commands",
                    border_style="blue",
                ))
                continue
            
            if user_input.lower() == "/tools":
                console.print(f"[dim]Available tools: {', '.join(default_tools)}[/dim]\n")
                continue
            
            console.print()
            console.print("[bold blue]Assistant:[/bold blue]")
            
            # Run query
            response = await run_query(
                prompt=user_input,
                allowed_tools=default_tools,
                permission_mode="acceptEdits"
            )
            
            # Display response
            if response:
                console.print(Markdown(response))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n\n[dim]Goodbye! 👋[/dim]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")
            import traceback
            traceback.print_exc()


def check_api_key() -> bool:
    """Check if API key is set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable not set.[/red]")
        console.print("[yellow]Please set it with: export ANTHROPIC_API_KEY='your-key'[/yellow]")
        return False
    return True


async def main() -> None:
    """Main entry point."""
    print_banner()
    
    if not check_api_key():
        sys.exit(1)
    
    console.print("[dim]✓ API key loaded[/dim]\n")
    
    await interactive_chat()


if __name__ == "__main__":
    asyncio.run(main())
