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
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Check if running in interactive mode
def is_interactive():
    """Check if running in an interactive terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()

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
class TimingStep:
    """Timing information for a single step."""
    step_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    
    def finish(self):
        """Mark step as finished and calculate duration."""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()


@dataclass
class AgentResult:
    """Result from an agent execution."""
    agent_name: str
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    timing_steps: List[TimingStep] = field(default_factory=list)
    # KPIs
    tool_calls_count: int = 0
    tool_calls_successful: int = 0
    tool_calls_failed: int = 0
    message_sent: bool = False
    target_reached: bool = False
    safety_constraints_followed: bool = True


class AgentRunner:
    """Runs tasks across multiple agents."""
    
    def __init__(self, mcp_url: str, auth_header: Optional[str] = None, progress_callback=None):
        self.mcp_url = mcp_url
        self.auth_header = auth_header
        self.results: List[AgentResult] = []
        self.progress_callback = progress_callback
    
    def _update_progress(self, agent_name: str, status: str):
        """Update progress callback if available."""
        if self.progress_callback:
            self.progress_callback(agent_name, status)
    
    async def run_anthropic_agent(self, task: str) -> AgentResult:
        """Run task with Anthropic (Claude) Agent."""
        start_time = datetime.now()
        timing_steps = []
        
        step = TimingStep("Initialization", datetime.now())
        timing_steps.append(step)
        self._update_progress("Anthropic Agent", "Starting...")
        try:
            anthropic_path = os.path.join(os.path.dirname(__file__), "anthropic_agent")
            # Temporarily modify sys.path to import from anthropic_agent
            original_path = sys.path[:]
            sys.path.insert(0, anthropic_path)
            try:
                # Import from anthropic_agent directory
                from mcp_config import build_mcp_server_config
                from oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage
                from claude_agent_sdk import query, ClaudeAgentOptions
            finally:
                # Restore original path
                sys.path[:] = original_path
            
            if not os.environ.get("ANTHROPIC_API_KEY"):
                step.finish()
                self._update_progress("Anthropic Agent", "❌ API key not set")
                return AgentResult(
                    agent_name="Anthropic Agent",
                    success=False,
                    output="",
                    error="ANTHROPIC_API_KEY not set",
                    timing_steps=timing_steps
                )
            
            step.finish()
            step = TimingStep("OAuth Setup", datetime.now())
            timing_steps.append(step)
            self._update_progress("Anthropic Agent", "Setting up OAuth...")
            base_url = self.mcp_url[:-4] if self.mcp_url.endswith("/mcp") else self.mcp_url
            storage = InMemoryTokenStorage()
            callback_server = CallbackServer(port=3030)
            callback_server.start()
            oauth_provider = create_oauth_provider(base_url, callback_server)
            step.finish()
            
            try:
                step = TimingStep("MCP Connection", datetime.now())
                timing_steps.append(step)
                self._update_progress("Anthropic Agent", "Connecting to MCP server...")
                mcp_servers = await build_mcp_server_config(
                    mcp_url=self.mcp_url,
                    auth_header=self.auth_header,
                    oauth_provider=oauth_provider,
                    storage=storage,
                    server_name="mcp_server"
                )
                step.finish()
                
                step = TimingStep("Agent Initialization", datetime.now())
                timing_steps.append(step)
                self._update_progress("Anthropic Agent", "Initializing Claude Agent...")
                options = ClaudeAgentOptions(
                    mcp_servers=mcp_servers,
                    permission_mode="bypassPermissions",
                    env={"ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY")}
                )
                step.finish()
                
                step = TimingStep("Task Execution", datetime.now())
                timing_steps.append(step)
                
                # Minimal instructions - let the agent be autonomous
                # Add agent identification requirement and task completion requirement
                interpreted_task = f"{task}\n\nIMPORTANT: When posting messages or providing output, always prefix with 'Anthropic Agent: ' followed by your message. Example: 'Anthropic Agent: My favorite color is Red.'\n\nCRITICAL: You must actually COMPLETE the task, not just start it. The task is only complete when you have successfully executed the final action (e.g., sent the message, posted the content, completed the operation). You may need to do multiple steps - do ALL of them. Only report completion when the task is truly finished."
                
                self._update_progress("Anthropic Agent", "Interpreting and executing task...")
                output_parts = []
                async for message in query(prompt=interpreted_task, options=options):
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                output_parts.append(block.text)
                step.finish()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                # Calculate KPIs
                output_str = "\n".join(output_parts)
                output_lower = output_str.lower()
                tool_calls_count = output_str.count("tool") + output_str.count("mcp")
                message_sent = "message" in output_lower and ("sent" in output_lower or "posted" in output_lower or "delivered" in output_lower)
                target_reached = self.mcp_url in output_str or "channel" in output_lower or "dm" in output_lower
                safety_followed = "public" not in output_lower and "general" not in output_lower
                
                return AgentResult(
                    agent_name="Anthropic Agent",
                    success=True,
                    output=output_str,
                    execution_time=execution_time,
                    timing_steps=timing_steps,
                    tool_calls_count=tool_calls_count,
                    tool_calls_successful=tool_calls_count if message_sent else 0,
                    message_sent=message_sent,
                    target_reached=target_reached,
                    safety_constraints_followed=safety_followed
                )
            finally:
                callback_server.stop()
                
        except Exception as e:
            if timing_steps and not timing_steps[-1].end_time:
                timing_steps[-1].finish()
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name="Anthropic Agent",
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time,
                timing_steps=timing_steps
            )
    
    async def run_langchain_agent(self, task: str) -> AgentResult:
        """Run task with Langchain Agent."""
        start_time = datetime.now()
        timing_steps = []
        
        step = TimingStep("Initialization", datetime.now())
        timing_steps.append(step)
        self._update_progress("Langchain Agent", "Starting...")
        try:
            langchain_path = os.path.join(os.path.dirname(__file__), "langchain_agent")
            sys.path.insert(0, langchain_path)
            # Import from langchain_agent directory
            from agent.graph import AgentConfig, run_agent_session
            from auth.oauth import CallbackServer, create_oauth_provider, InMemoryTokenStorage
            from langchain_core.messages import HumanMessage
            
            if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
                step.finish()
                self._update_progress("Langchain Agent", "❌ API key not set")
                return AgentResult(
                    agent_name="Langchain Agent",
                    success=False,
                    output="",
                    error="ANTHROPIC_API_KEY or OPENAI_API_KEY not set",
                    timing_steps=timing_steps
                )
            
            step.finish()
            step = TimingStep("OAuth Setup", datetime.now())
            timing_steps.append(step)
            self._update_progress("Langchain Agent", "Setting up OAuth...")
            base_url = self.mcp_url[:-4] if self.mcp_url.endswith("/mcp") else self.mcp_url
            storage = InMemoryTokenStorage()
            callback_server = CallbackServer(port=3031)
            callback_server.start()
            oauth_provider = create_oauth_provider(base_url, callback_server)
            step.finish()
            
            try:
                # Determine provider
                provider = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai"
                step = TimingStep("Provider Selection", datetime.now())
                timing_steps.append(step)
                self._update_progress("Langchain Agent", f"Using {provider} provider...")
                
                config = AgentConfig(
                    mcp_url=self.mcp_url,
                    auth_header=self.auth_header,
                    oauth_provider=oauth_provider,
                    provider=provider
                )
                step.finish()
                
                step = TimingStep("MCP Connection", datetime.now())
                timing_steps.append(step)
                self._update_progress("Langchain Agent", "Connecting to MCP server...")
                output_parts = []
                exec_step = None
                
                async def on_ready(agent, client, tools):
                    """Callback when agent is ready."""
                    nonlocal exec_step, output_parts
                    try:
                        step.finish()
                        exec_step = TimingStep("Task Execution", datetime.now())
                        timing_steps.append(exec_step)
                        self._update_progress("Langchain Agent", "Interpreting and executing task...")
                        
                        # Minimal instructions - let the agent be autonomous
                        # Add agent identification requirement
                        task_with_id = f"{task}\n\nIMPORTANT: When posting messages or providing output, always prefix with 'Langchain Agent: ' followed by your message. Example: 'Langchain Agent: My favorite color is Red.'"
                        messages = [HumanMessage(content=task_with_id)]
                        # Add timeout to prevent hanging
                        try:
                            result = await asyncio.wait_for(
                                agent.ainvoke({"messages": messages}),
                                timeout=180.0  # 3 minute timeout
                            )
                        except asyncio.TimeoutError:
                            output_parts.append("Error: Agent execution timed out after 3 minutes")
                            raise TimeoutError("Langchain agent execution timed out")
                        
                        if exec_step:
                            exec_step.finish()
                        
                        if "messages" in result:
                            for msg in result["messages"]:
                                if hasattr(msg, 'content'):
                                    output_parts.append(str(msg.content))
                                else:
                                    output_parts.append(str(msg))
                        else:
                            output_parts.append(str(result))
                    except Exception as e:
                        if exec_step:
                            exec_step.finish()
                        output_parts.append(f"Error: {str(e)}")
                        raise
                    finally:
                        try:
                            await client.close()
                        except:
                            pass
                
                await run_agent_session(config, on_ready)
                if timing_steps and not timing_steps[-1].end_time:
                    timing_steps[-1].finish()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                # Calculate KPIs
                output_str = "\n".join(output_parts)
                output_lower = output_str.lower()
                tool_calls_count = output_str.count("tool") + output_str.count("mcp")
                message_sent = "message" in output_lower and ("sent" in output_lower or "posted" in output_lower or "delivered" in output_lower)
                target_reached = self.mcp_url in output_str or "channel" in output_lower or "dm" in output_lower
                safety_followed = "public" not in output_lower and "general" not in output_lower
                
                return AgentResult(
                    agent_name="Langchain Agent",
                    success=True,
                    output=output_str,
                    execution_time=execution_time,
                    timing_steps=timing_steps,
                    tool_calls_count=tool_calls_count,
                    tool_calls_successful=tool_calls_count if message_sent else 0,
                    message_sent=message_sent,
                    target_reached=target_reached,
                    safety_constraints_followed=safety_followed
                )
            finally:
                callback_server.stop()
                
        except Exception as e:
            if timing_steps and not timing_steps[-1].end_time:
                timing_steps[-1].finish()
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name="Langchain Agent",
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time,
                timing_steps=timing_steps
            )
    
    async def run_openai_agent(self, task: str) -> AgentResult:
        """Run task with OpenAI Agent."""
        start_time = datetime.now()
        timing_steps = []
        
        step = TimingStep("Initialization", datetime.now())
        timing_steps.append(step)
        self._update_progress("OpenAI Agent", "Starting...")
        try:
            openai_path = os.path.join(os.path.dirname(__file__), "openai_agent")
            # Temporarily modify sys.path to import from openai_agent
            original_path = sys.path[:]
            sys.path.insert(0, openai_path)
            try:
                # Import from openai_agent directory
                from mcp_config import build_mcp_server
                from auth.oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage
                from agents import Agent, Runner
            finally:
                # Restore original path
                sys.path[:] = original_path
            
            if not os.environ.get("OPENAI_API_KEY"):
                step.finish()
                self._update_progress("OpenAI Agent", "❌ API key not set")
                return AgentResult(
                    agent_name="OpenAI Agent",
                    success=False,
                    output="",
                    error="OPENAI_API_KEY not set",
                    timing_steps=timing_steps
                )
            
            step.finish()
            step = TimingStep("OAuth Setup", datetime.now())
            timing_steps.append(step)
            self._update_progress("OpenAI Agent", "Setting up OAuth...")
            base_url = self.mcp_url[:-4] if self.mcp_url.endswith("/mcp") else self.mcp_url
            storage = InMemoryTokenStorage()
            callback_server = CallbackServer(port=3032)
            callback_server.start()
            oauth_provider = create_oauth_provider(base_url, callback_server)
            step.finish()
            
            try:
                step = TimingStep("MCP Connection", datetime.now())
                timing_steps.append(step)
                self._update_progress("OpenAI Agent", "Connecting to MCP server...")
                mcp_server = await build_mcp_server(
                    mcp_url=self.mcp_url,
                    auth_header=self.auth_header,
                    oauth_provider=oauth_provider,
                    storage=storage
                )
                
                await mcp_server.connect()
                step.finish()
                
                step = TimingStep("Agent Initialization", datetime.now())
                timing_steps.append(step)
                self._update_progress("OpenAI Agent", "Initializing OpenAI Agent...")
                
                model = os.environ.get("OPENAI_MODEL", "gpt-4o")
                agent = Agent(
                    name="OpenAI Agent",
                    instructions="You are an autonomous AI agent with access to MCP server tools. Use the available tools to complete tasks as requested. When posting messages or providing output, always prefix with 'OpenAI Agent: ' followed by your message. Example: 'OpenAI Agent: My favorite color is Red.'",
                    model=model,
                    mcp_servers=[mcp_server]
                )
                step.finish()
                
                step = TimingStep("Task Execution", datetime.now())
                timing_steps.append(step)
                
                # Minimal instructions - let the agent be autonomous
                # Add agent identification requirement and task completion requirement
                interpreted_task = f"{task}\n\nIMPORTANT: When posting messages or providing output, always prefix with 'OpenAI Agent: ' followed by your message. Example: 'OpenAI Agent: My favorite color is Red.'\n\nCRITICAL: You must actually COMPLETE the task, not just start it. The task is only complete when you have successfully executed the final action (e.g., sent the message, posted the content, completed the operation). You may need to do multiple steps - do ALL of them. Only report completion when the task is truly finished."
                
                self._update_progress("OpenAI Agent", "Interpreting and executing task...")
                result = await Runner.run(agent, interpreted_task)
                step.finish()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                output = result.final_output if result and result.final_output else "No output"
                
                await mcp_server.cleanup()
                
                # Calculate KPIs
                output_lower = output.lower()
                tool_calls_count = output.count("tool") + output.count("mcp")
                message_sent = "message" in output_lower and ("sent" in output_lower or "posted" in output_lower or "delivered" in output_lower)
                target_reached = self.mcp_url in output or "channel" in output_lower or "dm" in output_lower
                safety_followed = "public" not in output_lower and "general" not in output_lower
                
                return AgentResult(
                    agent_name="OpenAI Agent",
                    success=True,
                    output=output,
                    execution_time=execution_time,
                    timing_steps=timing_steps,
                    tool_calls_count=tool_calls_count,
                    tool_calls_successful=tool_calls_count if message_sent else 0,
                    message_sent=message_sent,
                    target_reached=target_reached,
                    safety_constraints_followed=safety_followed
                )
            finally:
                callback_server.stop()
                
        except Exception as e:
            if timing_steps and not timing_steps[-1].end_time:
                timing_steps[-1].finish()
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name="OpenAI Agent",
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time,
                timing_steps=timing_steps
            )
    
    async def run_agents(self, task: str, selected_agents: List[str]) -> List[AgentResult]:
        """Run task across selected agents."""
        results = []
        
        # Run agents sequentially for better progress visibility
        if "anthropic" in selected_agents:
            result = await self.run_anthropic_agent(task)
            results.append(result)
            self._update_progress("Anthropic Agent", "✅ Complete" if result.success else "❌ Failed")
        
        if "langchain" in selected_agents:
            result = await self.run_langchain_agent(task)
            results.append(result)
            self._update_progress("Langchain Agent", "✅ Complete" if result.success else "❌ Failed")
        
        if "openai" in selected_agents:
            result = await self.run_openai_agent(task)
            results.append(result)
            self._update_progress("OpenAI Agent", "✅ Complete" if result.success else "❌ Failed")
        
        return results


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
    try:
        selection = console.input("[bold cyan]Select agents (comma-separated, e.g., 1,2,3 or 'all'): [/bold cyan]").strip()
        if not selection:
            selection = "all"
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Using all agents by default[/yellow]")
        return ["anthropic", "langchain", "openai"]
    
    if selection.lower() == "all":
        return ["anthropic", "langchain", "openai"]
    
    selected = []
    for num in selection.split(","):
        num = num.strip()
        if num in agents:
            selected.append(agents[num][0])
    
    if not selected:
        console.print("[yellow]No valid agents selected. Using all agents.[/yellow]")
        return ["anthropic", "langchain", "openai"]
    
    return selected


def generate_timing_log(results: List[AgentResult], task: str, mcp_url: str) -> str:
    """Generate markdown log file with timing data."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_content = f"""# Agent Execution Timing Log

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Task:** {task}  
**MCP Server:** {mcp_url}

## Summary

| Agent | Status | Total Time | Success |
|-------|--------|------------|---------|
"""
    
    for result in results:
        status = "✅ Success" if result.success else "❌ Failed"
        log_content += f"| {result.agent_name} | {status} | {result.execution_time:.2f}s | {result.success} |\n"
    
    log_content += "\n## Detailed Timing Breakdown\n\n"
    
    for result in results:
        log_content += f"### {result.agent_name}\n\n"
        log_content += f"**Total Execution Time:** {result.execution_time:.2f}s\n\n"
        
        if result.timing_steps:
            log_content += "| Step | Duration | Percentage |\n"
            log_content += "|------|----------|------------|\n"
            
            for step in result.timing_steps:
                if step.duration is not None:
                    percentage = (step.duration / result.execution_time * 100) if result.execution_time > 0 else 0
                    log_content += f"| {step.step_name} | {step.duration:.2f}s | {percentage:.1f}% |\n"
        else:
            log_content += "*No timing data available*\n"
        
        if result.error:
            log_content += f"\n**Error:** {result.error}\n"
        
        log_content += "\n"
    
    # Find slowest steps
    log_content += "## Slowest Steps Across All Agents\n\n"
    all_steps = []
    for result in results:
        for step in result.timing_steps:
            if step.duration is not None:
                all_steps.append((result.agent_name, step.step_name, step.duration))
    
    all_steps.sort(key=lambda x: x[2], reverse=True)
    log_content += "| Agent | Step | Duration |\n"
    log_content += "|-------|------|----------|\n"
    for agent, step_name, duration in all_steps[:10]:  # Top 10 slowest
        log_content += f"| {agent} | {step_name} | {duration:.2f}s |\n"
    
    return log_content


def display_results(results: List[AgentResult], task: str, mcp_url: str):
    """Display results in a nice format."""
    console.print()
    console.print("╔══════════════════════════════════════════════════════════╗", style="bold green")
    console.print("║  📊 Execution Results                                   ║", style="bold green")
    console.print("╚══════════════════════════════════════════════════════════╝", style="bold green")
    console.print()
    
    # Summary table with KPIs
    table = Table(title="Execution Summary", box=box.ROUNDED)
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Time", justify="right", style="dim")
    table.add_column("Tools", justify="center", style="dim")
    table.add_column("Message", justify="center")
    table.add_column("Safety", justify="center")
    table.add_column("Error", style="red")

    for result in results:
        status = "✅ Success" if result.success else "❌ Failed"
        status_style = "green" if result.success else "red"
        time_str = f"{result.execution_time:.2f}s"
        tools_str = f"{result.tool_calls_successful}/{result.tool_calls_count}" if result.tool_calls_count > 0 else "N/A"
        message_str = "✅" if result.message_sent else "❌"
        safety_str = "✅" if result.safety_constraints_followed else "⚠️"
        error_str = result.error[:50] + "..." if result.error and len(result.error) > 50 else (result.error or "")

        table.add_row(
            result.agent_name,
            f"[{status_style}]{status}[/{status_style}]",
            time_str,
            tools_str,
            message_str,
            safety_str,
            error_str
        )

    console.print(table)
    console.print()
    
    # KPI Summary Table
    kpi_table = Table(title="Key Performance Indicators (KPIs)", box=box.ROUNDED)
    kpi_table.add_column("Agent", style="cyan")
    kpi_table.add_column("Tool Calls", justify="center")
    kpi_table.add_column("Success Rate", justify="center")
    kpi_table.add_column("Message Sent", justify="center")
    kpi_table.add_column("Target Reached", justify="center")
    kpi_table.add_column("Safety Followed", justify="center")
    
    for result in results:
        success_rate = f"{(result.tool_calls_successful/result.tool_calls_count*100):.1f}%" if result.tool_calls_count > 0 else "N/A"
        message_sent = "[green]✅ Yes[/green]" if result.message_sent else "[red]❌ No[/red]"
        target_reached = "[green]✅ Yes[/green]" if result.target_reached else "[red]❌ No[/red]"
        safety_followed = "[green]✅ Yes[/green]" if result.safety_constraints_followed else "[yellow]⚠️ No[/yellow]"
        kpi_table.add_row(
            result.agent_name,
            f"{result.tool_calls_count}",
            success_rate,
            message_sent,
            target_reached,
            safety_followed
        )
    
    console.print(kpi_table)
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
    elif args.no_interactive:
        console.print("[red]Error: --no-interactive requires --task and --agents[/red]")
        sys.exit(1)
    else:
        # Always try interactive mode - let it fail gracefully if not available
        console.print("[bold]Enter the task for the agents (they pick the color):[/bold]")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]- \"Make a short post about your favorite color (you choose) to the DM target\"[/dim]")
        console.print("[dim]- \"List available tools, then do a DM-only action using them\"[/dim]")
        console.print("[dim]- \"Summarize the latest messages in the DM channel\"[/dim]")
        console.print()
        console.print("[yellow]Safety reminder:[/yellow] Agents run in DM-only mode, must prefix with their agent name, must not post in public, and should keep responses short.")
        console.print("[yellow]Tip:[/yellow] Use --task/--agents flags for non-interactive runs; interactive mode simply takes the sentence you type here.")
        console.print()
        try:
            task = console.input("[bold cyan]Task: [/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[red]Error: Task input cancelled or not available[/red]")
            console.print("[yellow]Tip: Use --task flag for non-interactive mode[/yellow]")
            sys.exit(1)
    
    if not task or not task.strip():
        console.print("[red]Error: Task cannot be empty[/red]")
        sys.exit(1)
    
    task = task.strip()
    
    # Get selected agents
    if args.agents:
        if args.agents.lower() == "all":
            selected_agents = ["anthropic", "langchain", "openai"]
        else:
            selected_agents = [a.strip() for a in args.agents.split(",")]
    elif args.no_interactive:
        console.print("[red]Error: --no-interactive requires --agents[/red]")
        sys.exit(1)
    else:
        if not is_interactive():
            console.print("[red]Error: Not running in interactive terminal[/red]")
            console.print("[yellow]Tip: Use --agents flag, or run in an interactive terminal[/yellow]")
            sys.exit(1)
        
        try:
            selected_agents = select_agents()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Using all agents by default[/yellow]")
            selected_agents = ["anthropic", "langchain", "openai"]
    
    console.print()
    console.print(f"[bold]Task:[/bold] {task}")
    console.print(f"[bold]Selected Agents:[/bold] {', '.join(selected_agents)}")
    
    # Show MCP server selection
    # Extract server name from URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(args.mcp_url)
        mcp_server_name = parsed.netloc.split('.')[0] if parsed.netloc else parsed.path.split('/')[-2] if '/' in parsed.path else "MCP Server"
    except:
        mcp_server_name = args.mcp_url.split('/')[-2] if '/' in args.mcp_url else "MCP Server"
    
    console.print(f"[bold]MCP Server:[/bold] {args.mcp_url}")
    console.print(f"[green]✓ Default server selected: {mcp_server_name}[/green]")
    console.print()
    
    # Task interpretation and feasibility check
    console.print(Panel(
        "[bold]Task Interpretation:[/bold]\n\n"
        f"The agents will interpret: '{task}'\n\n"
        "Each agent will:\n"
        "  1. Analyze if the task is completable with available MCP tools\n"
        "  2. Report if the task cannot be completed before querying the server\n"
        "  3. Execute the task using the MCP server tools if feasible",
        title="Task Analysis",
        border_style="yellow"
    ))
    console.print()
    
    # Run agents with progress tracking
    def update_progress(agent_name: str, status: str):
        """Update progress display."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        console.print(f"[dim][{timestamp}][/dim] [cyan]{agent_name}:[/cyan] {status}")
    
    runner = AgentRunner(mcp_url=args.mcp_url, auth_header=args.auth_header, progress_callback=update_progress)
    
    console.print()
    console.print("[bold]Running agents sequentially...[/bold]")
    console.print()
    
    results = await runner.run_agents(task, selected_agents)
    
    console.print()  # New line after progress updates
    
    # Display results
    display_results(results, task, args.mcp_url)
    
    # Generate and save timing log
    log_content = generate_timing_log(results, task, args.mcp_url)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"agent_timing_log_{timestamp}.md"
    log_path = os.path.join(os.path.dirname(__file__), log_filename)
    
    try:
        with open(log_path, 'w') as f:
            f.write(log_content)
        console.print()
        console.print(f"[green]✅ Timing log saved to:[/green] {log_path}")
    except Exception as e:
        console.print(f"[yellow]⚠ Could not save timing log: {e}[/yellow]")
    
    # Exit status
    all_success = all(r.success for r in results)
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise from agent libraries
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    asyncio.run(main())
