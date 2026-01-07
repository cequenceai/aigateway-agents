#!/usr/bin/env python3
"""
Unified Agent Runner - Run tasks across multiple AI agents with MCP servers.

This CLI allows you to select which agents to use (Anthropic, Langchain, OpenAI)
and run the same task across all selected agents using a single MCP server.
"""

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich import box

console = Console()
logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from an agent execution."""
    agent_name: str
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0


class AgentRunner:
    """Runs tasks across multiple agents."""
    
    def __init__(self, mcp_url: str, auth_header: Optional[str] = None):
        self.mcp_url = mcp_url
        self.auth_header = auth_header
        self.results: List[AgentResult] = []
    
    async def run_anthropic_agent(self, task: str) -> AgentResult:
        """Run task with Anthropic (Claude) Agent."""
        start_time = datetime.now()
        try:
            anthropic_path = os.path.join(os.path.dirname(__file__), "anthropic_agent")
            sys.path.insert(0, anthropic_path)
            from mcp_config import build_mcp_server_config
            from oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage
            from claude_agent_sdk import query, ClaudeAgentOptions
            
            if not os.environ.get("ANTHROPIC_API_KEY"):
                return AgentResult(
                    agent_name="Anthropic Agent",
                    success=False,
                    output="",
                    error="ANTHROPIC_API_KEY not set"
                )
            
            base_url = self.mcp_url[:-4] if self.mcp_url.endswith("/mcp") else self.mcp_url
            storage = InMemoryTokenStorage()
            callback_server = CallbackServer(port=3030)
            callback_server.start()
            oauth_provider = create_oauth_provider(base_url, callback_server)
            
            try:
                mcp_servers = await build_mcp_server_config(
                    mcp_url=self.mcp_url,
                    auth_header=self.auth_header,
                    oauth_provider=oauth_provider,
                    storage=storage,
                    server_name="mcp_server"
                )
                
                options = ClaudeAgentOptions(
                    mcp_servers=mcp_servers,
                    permission_mode="bypassPermissions",
                    env={"ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY")}
                )
                
                output_parts = []
                async for message in query(prompt=task, options=options):
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                output_parts.append(block.text)
                
                execution_time = (datetime.now() - start_time).total_seconds()
                return AgentResult(
                    agent_name="Anthropic Agent",
                    success=True,
                    output="\n".join(output_parts),
                    execution_time=execution_time
                )
            finally:
                callback_server.stop()
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name="Anthropic Agent",
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time
            )
    
    async def run_langchain_agent(self, task: str) -> AgentResult:
        """Run task with Langchain Agent."""
        start_time = datetime.now()
        try:
            langchain_path = os.path.join(os.path.dirname(__file__), "langchain_agent")
            sys.path.insert(0, langchain_path)
            from agent.graph import AgentConfig, run_agent_session
            from auth.oauth import CallbackServer, create_oauth_provider, InMemoryTokenStorage
            from langchain_core.messages import HumanMessage
            
            if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
                return AgentResult(
                    agent_name="Langchain Agent",
                    success=False,
                    output="",
                    error="ANTHROPIC_API_KEY or OPENAI_API_KEY not set"
                )
            
            base_url = self.mcp_url[:-4] if self.mcp_url.endswith("/mcp") else self.mcp_url
            storage = InMemoryTokenStorage()
            callback_server = CallbackServer(port=3031)
            callback_server.start()
            oauth_provider = create_oauth_provider(base_url, callback_server)
            
            try:
                # Determine provider
                provider = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai"
                
                config = AgentConfig(
                    mcp_url=self.mcp_url,
                    auth_header=self.auth_header,
                    oauth_provider=oauth_provider,
                    provider=provider
                )
                
                output_parts = []
                
                async def on_ready(agent, client, tools):
                    """Callback when agent is ready."""
                    try:
                        messages = [HumanMessage(content=task)]
                        result = await agent.ainvoke({"messages": messages})
                        
                        if "messages" in result:
                            for msg in result["messages"]:
                                if hasattr(msg, 'content'):
                                    output_parts.append(str(msg.content))
                                else:
                                    output_parts.append(str(msg))
                        else:
                            output_parts.append(str(result))
                    finally:
                        try:
                            await client.close()
                        except:
                            pass
                
                await run_agent_session(config, on_ready)
                
                execution_time = (datetime.now() - start_time).total_seconds()
                return AgentResult(
                    agent_name="Langchain Agent",
                    success=True,
                    output="\n".join(output_parts),
                    execution_time=execution_time
                )
            finally:
                callback_server.stop()
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name="Langchain Agent",
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time
            )
    
    async def run_openai_agent(self, task: str) -> AgentResult:
        """Run task with OpenAI Agent."""
        start_time = datetime.now()
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "openai_agent"))
            from mcp_config import build_mcp_server
            from auth.oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage
            from agents import Agent, Runner
            
            if not os.environ.get("OPENAI_API_KEY"):
                return AgentResult(
                    agent_name="OpenAI Agent",
                    success=False,
                    output="",
                    error="OPENAI_API_KEY not set"
                )
            
            base_url = self.mcp_url[:-4] if self.mcp_url.endswith("/mcp") else self.mcp_url
            storage = InMemoryTokenStorage()
            callback_server = CallbackServer(port=3032)
            callback_server.start()
            oauth_provider = create_oauth_provider(base_url, callback_server)
            
            try:
                mcp_server = await build_mcp_server(
                    mcp_url=self.mcp_url,
                    auth_header=self.auth_header,
                    oauth_provider=oauth_provider,
                    storage=storage
                )
                
                await mcp_server.connect()
                
                model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
                agent = Agent(
                    name="OpenAI Agent",
                    instructions="You are a helpful assistant with access to MCP server tools.",
                    model=model,
                    mcp_servers=[mcp_server]
                )
                
                result = await Runner.run(agent, task)
                
                execution_time = (datetime.now() - start_time).total_seconds()
                output = result.final_output if result and result.final_output else "No output"
                
                await mcp_server.cleanup()
                
                return AgentResult(
                    agent_name="OpenAI Agent",
                    success=True,
                    output=output,
                    execution_time=execution_time
                )
            finally:
                callback_server.stop()
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name="OpenAI Agent",
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time
            )
    
    async def run_agents(self, task: str, selected_agents: List[str]) -> List[AgentResult]:
        """Run task across selected agents."""
        results = []
        
        tasks = []
        if "anthropic" in selected_agents:
            tasks.append(self.run_anthropic_agent(task))
        if "langchain" in selected_agents:
            tasks.append(self.run_langchain_agent(task))
        if "openai" in selected_agents:
            tasks.append(self.run_openai_agent(task))
        
        if not tasks:
            return results
        
        # Run agents in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent_name = ["Anthropic Agent", "Langchain Agent", "OpenAI Agent"][i]
                processed_results.append(AgentResult(
                    agent_name=agent_name,
                    success=False,
                    output="",
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results


def print_banner():
    """Print application banner."""
    console.print()
    console.print("╔══════════════════════════════════════════════════════════╗", style="bold cyan")
    console.print("║  🤖 Unified Agent Runner - Multi-Agent Task Execution     ║", style="bold cyan")
    console.print("╚══════════════════════════════════════════════════════════╝", style="bold cyan")
    console.print()


def select_agents() -> List[str]:
    """Interactive agent selection."""
    console.print()
    console.print("[bold]Available Agents:[/bold]")
    console.print()
    
    agents = {
        "1": ("anthropic", "Anthropic Agent (Claude Agent SDK)", "blue"),
        "2": ("langchain", "Langchain Agent (Langchain MCP)", "green"),
        "3": ("openai", "OpenAI Agent (OpenAI Agents SDK)", "yellow")
    }
    
    for key, (id, name, color) in agents.items():
        console.print(f"  [{color}]{key}[/{color}]. {name}")
    
    console.print()
    selection = Prompt.ask(
        "[bold]Select agents (comma-separated, e.g., 1,2,3 or 'all'):[/bold]",
        default="all"
    )
    
    if selection.lower() == "all":
        return ["anthropic", "langchain", "openai"]
    
    selected = []
    for num in selection.split(","):
        num = num.strip()
        if num in agents:
            selected.append(agents[num][0])
    
    if not selected:
        console.print("[red]No valid agents selected. Using all agents.[/red]")
        return ["anthropic", "langchain", "openai"]
    
    return selected


def display_results(results: List[AgentResult], task: str):
    """Display results in a nice format."""
    console.print()
    console.print("╔══════════════════════════════════════════════════════════╗", style="bold green")
    console.print("║  📊 Execution Results                                   ║", style="bold green")
    console.print("╚══════════════════════════════════════════════════════════╝", style="bold green")
    console.print()
    
    # Summary table
    table = Table(title="Execution Summary", box=box.ROUNDED)
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Time", justify="right", style="dim")
    table.add_column("Error", style="red")
    
    for result in results:
        status = "✅ Success" if result.success else "❌ Failed"
        status_style = "green" if result.success else "red"
        time_str = f"{result.execution_time:.2f}s"
        error_str = result.error[:50] + "..." if result.error and len(result.error) > 50 else (result.error or "")
        
        table.add_row(
            result.agent_name,
            f"[{status_style}]{status}[/{status_style}]",
            time_str,
            error_str
        )
    
    console.print(table)
    console.print()
    
    # Detailed results
    for result in results:
        if result.success:
            console.print(Panel(
                Markdown(result.output) if result.output else "[dim]No output[/dim]",
                title=f"[bold green]✅ {result.agent_name}[/bold green]",
                border_style="green",
                title_align="left"
            ))
        else:
            console.print(Panel(
                f"[red]{result.error or 'Unknown error'}[/red]",
                title=f"[bold red]❌ {result.agent_name}[/bold red]",
                border_style="red",
                title_align="left"
            ))
        console.print()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run tasks across multiple AI agents with MCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--mcp-url",
        required=True,
        help="MCP server URL (e.g., https://server.com/mcp)"
    )
    parser.add_argument(
        "--auth-header",
        help="Static authorization header (e.g., 'Bearer token')"
    )
    parser.add_argument(
        "--task",
        help="Task to execute (if not provided, will prompt)"
    )
    parser.add_argument(
        "--agents",
        help="Comma-separated list of agents (anthropic,langchain,openai) or 'all'"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive mode (requires --task and --agents)"
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    # Get task
    if args.task:
        task = args.task
    else:
        console.print("[bold]Enter the task for the agents:[/bold]")
        console.print("[dim]Example: 'Send a message to user Abhinav saying Hello'[/dim]")
        console.print()
        task = Prompt.ask("[bold]Task[/bold]")
    
    if not task:
        console.print("[red]Error: Task cannot be empty[/red]")
        sys.exit(1)
    
    # Get selected agents
    if args.agents:
        if args.agents.lower() == "all":
            selected_agents = ["anthropic", "langchain", "openai"]
        else:
            selected_agents = [a.strip() for a in args.agents.split(",")]
    else:
        selected_agents = select_agents()
    
    console.print()
    console.print(f"[bold]Task:[/bold] {task}")
    console.print(f"[bold]Selected Agents:[/bold] {', '.join(selected_agents)}")
    console.print(f"[bold]MCP Server:[/bold] {args.mcp_url}")
    console.print()
    
    # Check if task is completable
    console.print(Panel(
        "[bold]Analyzing task...[/bold]\n\n"
        "If this task cannot be completed with the available MCP server tools, "
        "agents will report this before attempting to query the server.",
        title="Task Analysis",
        border_style="yellow"
    ))
    console.print()
    
    # Run agents
    runner = AgentRunner(mcp_url=args.mcp_url, auth_header=args.auth_header)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task_progress = progress.add_task("[cyan]Running agents...", total=None)
        results = await runner.run_agents(task, selected_agents)
        progress.update(task_progress, completed=True)
    
    # Display results
    display_results(results, task)
    
    # Exit status
    all_success = all(r.success for r in results)
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise from agent libraries
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    asyncio.run(main())
