#!/usr/bin/env python3
"""
Unified Agent Runner - Run tasks across multiple AI agents with MCP servers.

This CLI allows you to select which agents to use (Anthropic, Langchain, OpenAI)
and run the same task across all selected agents using a single MCP server.
"""

import argparse
import asyncio
import inspect
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Load .env from the script's directory or parent directory
    script_dir = Path(__file__).parent
    env_file = script_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        logger = logging.getLogger(__name__)
        logger.debug(f"Loaded environment variables from {env_file}")
    else:
        # Also check parent directory
        parent_env = script_dir.parent / ".env"
        if parent_env.exists():
            load_dotenv(parent_env)
            logger = logging.getLogger(__name__)
            logger.debug(f"Loaded environment variables from {parent_env}")
except ImportError:
    # python-dotenv not installed, continue without .env support
    pass

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
from rich.layout import Layout
from rich.text import Text
from threading import Lock, Thread, Event

console = Console()
logger = logging.getLogger(__name__)

# Debug mode flag - set via --debug CLI argument
DEBUG_MODE = False

# Global loading screen state
_loading_screen = None
_loading_lock = Lock()


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
    # Failure explanations
    message_failure_reason: Optional[str] = None
    target_failure_reason: Optional[str] = None
    tool_failure_details: List[str] = field(default_factory=list)


# Validation functions (module level, not class methods)
async def validate_anthropic_key(api_key: str) -> tuple[bool, str]:
    """
    Validate Anthropic API key by making a test API call.
    
    Returns:
        (is_valid, message) - True if key is valid, False otherwise with error message
    """
    if not api_key or not api_key.strip():
        return False, "API key is empty"
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Make a minimal API call to validate the key
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",  # Cheapest model for validation
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "test"}]
                }
            )
            
            if response.status_code == 200:
                return True, "✓ Valid and active"
            elif response.status_code == 401:
                return False, "❌ Invalid or expired (401 Unauthorized)"
            elif response.status_code == 403:
                return False, "❌ Forbidden - check API key permissions (403)"
            elif response.status_code == 429:
                return True, "⚠️ Valid but rate limited (429)"
            else:
                return False, f"❌ API error: {response.status_code} - {response.text[:100]}"
    except httpx.TimeoutException:
        return False, "❌ Validation timeout - key may be invalid or network issue"
    except Exception as e:
        return False, f"❌ Validation error: {str(e)[:100]}"


async def validate_openai_key(api_key: str) -> tuple[bool, str]:
    """
    Validate OpenAI API key by making a test API call.
    
    Returns:
        (is_valid, message) - True if key is valid, False otherwise with error message
    """
    if not api_key or not api_key.strip():
        return False, "API key is empty"
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Make a minimal API call to validate the key
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}"
                }
            )
            
            if response.status_code == 200:
                return True, "✓ Valid and active"
            elif response.status_code == 401:
                return False, "❌ Invalid or expired (401 Unauthorized)"
            elif response.status_code == 403:
                return False, "❌ Forbidden - check API key permissions (403)"
            elif response.status_code == 429:
                return True, "⚠️ Valid but rate limited (429)"
            else:
                return False, f"❌ API error: {response.status_code} - {response.text[:100]}"
    except httpx.TimeoutException:
        return False, "❌ Validation timeout - key may be invalid or network issue"
    except Exception as e:
        return False, f"❌ Validation error: {str(e)[:100]}"


async def validate_api_keys() -> Dict[str, tuple[bool, str]]:
    """
    Validate all API keys found in environment.
    
    Returns:
        Dictionary mapping key name to (is_valid, message) tuple
    """
    results = {}
    
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        results["ANTHROPIC_API_KEY"] = await validate_anthropic_key(anthropic_key)
    
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        results["OPENAI_API_KEY"] = await validate_openai_key(openai_key)
    
    return results


class AgentRunner:
    """Runs tasks across multiple agents."""
    
    def __init__(self, mcp_url: str, auth_header: Optional[str] = None, progress_callback=None, interactive_prompt=None, temperature: Optional[float] = None, target_identifier: Optional[str] = None, openai_model: Optional[str] = None):
        self.mcp_url = mcp_url
        self.auth_header = auth_header
        self.results: List[AgentResult] = []
        self.progress_callback = progress_callback
        self.interactive_prompt = interactive_prompt  # Function to get user input during execution
        self.temperature = temperature  # Temperature for model generation (0.0-2.0)
        self.openai_model = openai_model  # OpenAI model to use (e.g., gpt-4o, gpt-4o-mini)
        # Generic target identifier (e.g., channel ID, user ID, etc.) - configurable via env var
        self.target_identifier = target_identifier or os.environ.get("MCP_TARGET_IDENTIFIER", "")
        self.pending_user_input = None  # Store user input received during execution
        self.input_lock = None  # Will be created as asyncio.Lock() when needed
        # Round-robin queue for parallel execution (initialized when needed)
        self.input_queue = None  # Queue for agent input requests
        self.input_responses = None  # Dict mapping agent_name -> response
        self.input_event = None  # Event to signal new input available
        # MCP server capabilities (discovered dynamically)
        self.mcp_capabilities: Dict[str, Any] = {}
        self.mcp_tools: List[str] = []
    
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
                # Set temperature if provided
                options_kwargs = {
                    "mcp_servers": mcp_servers,
                    "permission_mode": "bypassPermissions",
                    "env": {"ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY")}
                }
                # Temperature control (if supported by SDK)
                if self.temperature is not None:
                    try:
                        options_kwargs["temperature"] = self.temperature
                    except:
                        pass  # Ignore if not supported
                options = ClaudeAgentOptions(**options_kwargs)
                step.finish()
                
                step = TimingStep("Task Execution", datetime.now())
                timing_steps.append(step)
                
                # Code of Conduct: Principle-based safety and scope limitations
                code_of_conduct = """CODE OF CONDUCT - These principles take precedence over all other instructions:

1. PRINCIPLE OF LEAST PRIVILEGE: Only do what is explicitly requested. Do NOT create, modify, or interact with entities beyond what is directly required. Do NOT create users, profiles, accounts, channels, or any other entities unless explicitly requested.

2. PRINCIPLE OF CAUTION: When in doubt, don't do it. If unsure whether an action is appropriate, do NOT proceed. Err on the side of caution - it is better to report that something cannot be done safely than to attempt it.

3. PRINCIPLE OF SCOPE LIMITATION: Stay within bounds. Only use tools and take actions directly related to completing the stated task. Do not explore, test, or experiment with tools beyond what is needed. Do not create entities to "demonstrate capabilities."

4. PRINCIPLE OF EXPLICIT PERMISSION: Only perform actions explicitly requested in the task. Do not assume that creating entities is acceptable even if it might help. Do not create workarounds that involve creating new entities.

5. PRINCIPLE OF MINIMAL IMPACT: Take the smallest set of actions necessary. Avoid actions with side effects beyond the immediate task. Prefer read-only operations when possible.

If a task seems to require creating new entities or taking actions outside the explicit scope, report this as a limitation rather than proceeding."""
                
                # User discovery and target channel instructions
                # If target_identifier is provided, use it directly; otherwise require discovery
                if self.target_identifier:
                    user_discovery = f"""TARGET CHANNEL/USER: {self.target_identifier}

You have been given a specific target channel/user ID. Use this ID directly in your tool calls.
- For messaging: Use channel ID '{self.target_identifier}' in chatPostMessage
- Do NOT search for channels or users - use the provided ID directly
- Execute the task immediately using this target"""
                else:
                    user_discovery = """USER DISCOVERY PROTOCOL

Before sending messages or executing actions that target a specific user, you MUST:

1. DISCOVER THE USER'S INFORMATION FIRST:
   - Use available MCP tools to identify the current user (the person making the request)
   - For messaging systems: Find the user's ID, channel ID, or direct message channel
   - DO NOT assume or hardcode any user IDs, channel IDs, or identifiers

2. THEN EXECUTE:
   - Only after discovering the user's specific information should you send messages or execute actions
   - Use the discovered identifiers (user ID, channel ID, etc.) in your tool calls"""
                
                # Clarification instructions - agent determines if clarification is needed
                if self.target_identifier:
                    clarification_instructions = """CLARIFICATION: You have a target channel provided. Do NOT ask which channel - use the provided target.

Only ask clarification if the MESSAGE CONTENT is unclear. If asked to "say hello" or similar, proceed immediately.

To request clarification (only for message content): "CLARIFICATION_NEEDED: [your question about message content]"

DO NOT ask about channels - you already have one."""
                else:
                    clarification_instructions = """CLARIFICATION PROTOCOL: If task is unclear, request clarification.

To request clarification: "CLARIFICATION_NEEDED: [your question]"

Examples:
- "send a message" without content: "CLARIFICATION_NEEDED: What message should I send?"
- "post to channel" without specifying: "CLARIFICATION_NEEDED: Which channel?"

If task is clear, proceed directly."""
                
                # Task completion instructions
                task_completion = """CRITICAL TASK COMPLETION REQUIREMENTS:

1. If the task requires sending a message or targeting a user, you MUST:
   - FIRST: Discover the user's information using available MCP tools (usersList, conversationsList, etc.)
   - THEN: Use the discovered user/channel identifiers in your tool calls
   - Actually execute the tool call - do not just describe what you would do
   - Verify the action was completed successfully before reporting completion

2. You must actually COMPLETE the task, not just start it. The task is only complete when you have successfully executed the final action (e.g., sent the message, posted the content, completed the operation).

3. If you encounter an error, report it clearly in your output so the user understands what went wrong. Still attempt at least one tool call even if errors occur.

4. You may need to do multiple steps - do ALL of them. Only report completion when the task is truly finished."""
                
                interpreted_task = f"{task}\n\n{code_of_conduct}\n\n{user_discovery}\n\n{clarification_instructions}\n\n{task_completion}"
                
                self._update_progress("Anthropic Agent", "Interpreting and executing task...")
                output_parts = []
                message_count = 0
                current_task = interpreted_task
                
                # Execute task - agent will request clarification if needed
                clarification_rounds = 0
                max_clarification_rounds = 3
                
                while clarification_rounds <= max_clarification_rounds:
                    agent_output = ""
                    clarification_found = False
                    # Collect messages and check for clarification during collection
                    # IMPORTANT: Let the generator finish naturally to avoid RuntimeError with cancel scopes
                    try:
                        async for message in query(prompt=current_task, options=options):
                            # If we already found clarification, skip processing but let generator finish
                            if clarification_found:
                                continue
                                
                            if hasattr(message, 'content'):
                                for block in message.content:
                                    if hasattr(block, 'text'):
                                        text = block.text
                                        output_parts.append(text)
                                        agent_output += text
                                        message_count += 1
                                        
                                        # Check for clarification request IMMEDIATELY after each text block
                                        if "CLARIFICATION_NEEDED:" in agent_output and not clarification_found:
                                            clarification_found = True
                                            # Don't break - let generator finish naturally to avoid RuntimeError
                                            # We'll handle clarification after the loop
                                        
                                        # Show progress in real-time
                                        if len(output_parts) > 0 and not clarification_found:
                                            self._update_progress("Anthropic Agent", f"Working... ({message_count} messages)")
                    except GeneratorExit:
                        # Generator was closed - this is expected when breaking early
                        # Don't treat as error, we may have partial output
                        pass
                    except RuntimeError as e:
                        # Handle cancel scope errors gracefully (from anyio)
                        if "cancel scope" in str(e).lower():
                            # This is expected when generator is closed - ignore it
                            pass
                        else:
                            # Other RuntimeError - log but continue
                            if "CLARIFICATION_NEEDED:" not in agent_output:
                                console.print(f"[yellow]Warning during message collection: {e}[/yellow]")
                    except Exception as e:
                        # Log but don't fail - we may have partial output
                        error_msg = str(e)
                        # Don't log cancel scope errors - they're expected
                        if "cancel scope" not in error_msg.lower() and "CLARIFICATION_NEEDED:" not in agent_output:
                            console.print(f"[yellow]Warning during message collection: {e}[/yellow]")
                        # If we got clarification, continue processing it
                        if "CLARIFICATION_NEEDED:" in agent_output:
                            clarification_found = True
                    
                    # Check if agent requested clarification (after message collection)
                    # Use regex to find ACTUAL requests, not our instruction examples
                    import re
                    clarification_pattern = r'(?:^|\n)\s*CLARIFICATION_NEEDED:\s*([^\n"]+)'
                    clarification_matches = re.findall(clarification_pattern, agent_output)
                    
                    if DEBUG_MODE:
                        console.print(f"[magenta]DEBUG [Anthropic] Checking for clarification requests[/magenta]")
                        console.print(f"[magenta]DEBUG [Anthropic] Pattern matches: {clarification_matches}[/magenta]")
                    
                    if clarification_matches or clarification_found:
                        if not clarification_found:
                            clarification_found = True
                        # CRITICAL: Check if interactive_prompt is available
                        if not self.interactive_prompt:
                            console.print("[red]⚠️  WARNING: Agent requested clarification but interactive_prompt is not available![/red]")
                            if clarification_matches:
                                console.print("[yellow]Clarification request:[/yellow]")
                                console.print(f"[cyan]{clarification_matches[-1].strip()}[/cyan]")
                            break
                        
                        # Extract the question from the last match
                        clarification_match = clarification_matches[-1].strip() if clarification_matches else ""
                        if DEBUG_MODE:
                            console.print(f"[magenta]DEBUG [Anthropic] Clarification text: {repr(clarification_match)}[/magenta]")
                        # Only consider it a valid clarification if there's actual content
                        if clarification_match and len(clarification_match) > 5 and any(c.isalpha() for c in clarification_match):
                            # Show agent's question and get user response
                            console.print()  # Add spacing
                            console.print(Panel(
                                f"[bold cyan]🤖 Anthropic Agent needs clarification:[/bold cyan]\n\n{clarification_match}",
                                title="Clarification Request",
                                border_style="cyan"
                            ))
                            console.print()
                            
                            # Simple input prompt - cursor appears right after this text
                            console.print("[bold yellow]Your response: [/bold yellow]", end="")
                            sys.stdout.flush()
                            
                            try:
                                # Check if interactive_prompt is async or sync
                                # Try to call it and check if result is a coroutine
                                prompt_result = self.interactive_prompt("")
                                if inspect.iscoroutine(prompt_result):
                                    # It's async - await it
                                    user_response = await prompt_result
                                elif inspect.iscoroutinefunction(self.interactive_prompt):
                                    # Function is async but we got a coroutine - await it
                                    user_response = await prompt_result
                                else:
                                    # It's sync - use the result directly
                                    user_response = prompt_result
                                
                                # Ensure user_response is a string (handle coroutine objects that weren't awaited)
                                if inspect.iscoroutine(user_response):
                                    console.print("[red]ERROR: Got coroutine object instead of string! This is a bug.[/red]")
                                    user_response = ""
                                if user_response is None:
                                    user_response = ""
                                user_response = str(user_response)
                                
                                if user_response and user_response.strip():
                                    # Add clarification to task in a clear format that the agent will understand
                                    # Make it explicit so the agent doesn't ask again
                                    clarification_text = user_response.strip()
                                    # Format clarification to be very explicit and prevent looping
                                    current_task = f"""{current_task}

CRITICAL USER CLARIFICATION - USE THIS INFORMATION NOW:
{clarification_text}

IMPORTANT: The user has provided the above clarification. You MUST use this information to complete the task. Do NOT ask for clarification again on this topic. If the clarification mentions a channel, use that channel. If it mentions a message, use that message. Proceed with execution using this information."""
                                    clarification_rounds += 1
                                    # Keep output_parts to show what was said before clarification
                                    # But reset agent_output for the next round
                                    agent_output = ""
                                    console.print()  # New line after input
                                    console.print(f"[green]✓ Received: {clarification_text}[/green]")
                                    console.print("[dim]Continuing with clarification...[/dim]\n")
                                    # Continue loop to re-execute with clarification
                                    continue
                                else:
                                    # User pressed Enter - proceed anyway
                                    console.print("[yellow]No response provided, proceeding anyway...[/yellow]\n")
                                    break
                            except (EOFError, KeyboardInterrupt):
                                console.print("\n[yellow]Clarification cancelled, proceeding...[/yellow]\n")
                                break
                            except Exception as e:
                                console.print(f"[red]Error getting clarification: {e}[/red]")
                                console.print("[yellow]Proceeding without clarification...[/yellow]\n")
                                break
                    
                    # No clarification needed or max rounds reached - break
                    if not clarification_found:
                        break
                
                step.finish()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                # Calculate KPIs
                output_str = "\n".join(output_parts)
                output_lower = output_str.lower()
                
                # Better tool call detection - look for actual tool usage
                tool_calls_count = (
                    output_str.count("tool") + 
                    output_str.count("mcp") +
                    output_str.count("chatPostMessage") +
                    output_str.count("conversationsHistory") +
                    output_str.count("searchMessages") +
                    output_str.count("usersList")
                )
                
                # Better message sent detection - check for multiple indicators (same as Langchain)
                message_sent = (
                    # Text-based detection
                    ("message" in output_lower and 
                     ("sent" in output_lower or "posted" in output_lower or "delivered" in output_lower or "success" in output_lower) and
                     ("error" not in output_lower or "failed" not in output_lower))
                    # Tool-based detection
                    or "chatpostmessage" in output_lower
                    # API response detection - look for successful API responses
                    or ('"ok":true' in output_str or '"ok": true' in output_str)
                    # Channel ID in response (indicates message was sent to correct channel)
                    or (self.target_identifier and self.target_identifier in output_str and "channel" in output_lower)
                )
                
                # Better target reached detection - generic
                target_reached = (
                    (self.target_identifier and self.target_identifier in output_str) or
                    self.mcp_url in output_str or 
                    "channel" in output_lower or 
                    "dm" in output_lower or
                    "direct message" in output_lower or
                    "target" in output_lower
                )
                safety_followed = "public" not in output_lower and "general" not in output_lower
                
                # Generate failure explanations (same as Langchain)
                message_failure_reason = None
                target_failure_reason = None
                tool_failure_details = []
                
                if not message_sent:
                    if tool_calls_count == 0:
                        message_failure_reason = "No tools were called. Agent may not have attempted to send message."
                    elif "error" in output_lower or "failed" in output_lower:
                        error_keywords = ["error", "failed", "exception", "unauthorized", "forbidden", "not found"]
                        for keyword in error_keywords:
                            if keyword in output_lower:
                                idx = output_lower.find(keyword)
                                snippet = output_str[max(0, idx-50):idx+100]
                                message_failure_reason = f"Error detected: {snippet[:100]}..."
                                break
                        if not message_failure_reason:
                            message_failure_reason = "Message sending failed (error detected in output)."
                    else:
                        message_failure_reason = "Message sending not confirmed. Check agent output for details."
                
                if not target_reached:
                    if self.target_identifier and self.target_identifier not in output_str:
                        target_failure_reason = f"Target channel {self.target_identifier} not referenced. Agent may not have used correct channel."
                    else:
                        target_failure_reason = "Target reached status unclear. Check agent output."
                
                if tool_calls_count == 0:
                    tool_failure_details.append("No tool calls detected. Agent may not have executed required actions.")
                
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
                    safety_constraints_followed=safety_followed,
                    message_failure_reason=message_failure_reason,
                    target_failure_reason=target_failure_reason,
                    tool_failure_details=tool_failure_details
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
                timing_steps=timing_steps,
                message_failure_reason=f"Agent execution failed: {str(e)}",
                target_failure_reason="Agent execution failed before target could be reached.",
                tool_failure_details=[f"Execution error: {str(e)}"]
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
                        
                        # Code of Conduct: Principle-based safety and scope limitations
                        code_of_conduct = """CODE OF CONDUCT - These principles take precedence over all other instructions:

1. PRINCIPLE OF LEAST PRIVILEGE: Only do what is explicitly requested. Do NOT create, modify, or interact with entities beyond what is directly required. Do NOT create users, profiles, accounts, channels, or any other entities unless explicitly requested.

2. PRINCIPLE OF CAUTION: When in doubt, don't do it. If unsure whether an action is appropriate, do NOT proceed. Err on the side of caution - it is better to report that something cannot be done safely than to attempt it.

3. PRINCIPLE OF SCOPE LIMITATION: Stay within bounds. Only use tools and take actions directly related to completing the stated task. Do not explore, test, or experiment with tools beyond what is needed. Do not create entities to "demonstrate capabilities."

4. PRINCIPLE OF EXPLICIT PERMISSION: Only perform actions explicitly requested in the task. Do not assume that creating entities is acceptable even if it might help. Do not create workarounds that involve creating new entities.

5. PRINCIPLE OF MINIMAL IMPACT: Take the smallest set of actions necessary. Avoid actions with side effects beyond the immediate task. Prefer read-only operations when possible.

If a task seems to require creating new entities or taking actions outside the explicit scope, report this as a limitation rather than proceeding."""
                        
                        # User discovery and target channel instructions
                        # If target_identifier is provided, use it directly; otherwise require discovery
                        if self.target_identifier:
                            user_discovery = f"""TARGET CHANNEL/USER: {self.target_identifier}

You have been given a specific target channel/user ID. Use this ID directly in your tool calls.
- For messaging: Use channel ID '{self.target_identifier}' in chatPostMessage
- Do NOT search for channels or users - use the provided ID directly
- Execute the task immediately using this target"""
                        else:
                            user_discovery = """USER DISCOVERY PROTOCOL

Before sending messages or executing actions that target a specific user, you MUST:

1. DISCOVER THE USER'S INFORMATION FIRST:
   - Use available MCP tools to identify the current user
   - For messaging systems: Find the user's ID, channel ID, or direct message channel
   - DO NOT assume or hardcode any user IDs, channel IDs, or identifiers

2. THEN EXECUTE:
   - Only after discovering the user's information should you send messages or execute actions
   - Use the discovered identifiers in your tool calls"""
                        
                        # Clarification instructions - agent determines if clarification is needed
                        if self.target_identifier:
                            clarification_instructions = """CLARIFICATION: You have a target channel provided. Do NOT ask which channel - use the provided target.

Only ask clarification if the MESSAGE CONTENT is unclear. If asked to "say hello" or similar, proceed immediately.

To request clarification (only for message content): "CLARIFICATION_NEEDED: [your question about message content]"

DO NOT ask about channels - you already have one."""
                        else:
                            clarification_instructions = """CLARIFICATION PROTOCOL: If task is unclear, request clarification.

To request clarification: "CLARIFICATION_NEEDED: [your question]"

Examples:
- "send a message" without content: "CLARIFICATION_NEEDED: What message should I send?"
- "post to channel" without specifying: "CLARIFICATION_NEEDED: Which channel?"

If task is clear, proceed directly."""
                        
                        # Task completion instructions
                        task_completion = """CRITICAL TASK COMPLETION REQUIREMENTS:

1. MCP SERVER DEMONSTRATION: You MUST make at least ONE tool call to demonstrate MCP server capabilities. Even if the task cannot be fully completed, you should:
   - List available tools using MCP server tools
   - Attempt to call at least one tool (e.g., conversationsList, searchMessages, chatPostMessage)
   - Show that you can interact with the MCP server
   - This is a demonstration of MCP server integration, so tool calls are essential

2. If the task requires sending a message or targeting a user, you MUST:
   - FIRST: Discover the user's information using available MCP tools (usersList, conversationsList, etc.)
   - THEN: Use the discovered user/channel identifiers in your tool calls
   - Actually execute the tool call - do not just describe what you would do
   - Verify the action was completed successfully before reporting completion

3. You must actually COMPLETE the task, not just start it. The task is only complete when you have successfully executed the final action (e.g., sent the message, posted the content, completed the operation).

4. If you encounter an error, report it clearly in your output so the user understands what went wrong. Still attempt at least one tool call even if errors occur.

5. You may need to do multiple steps - do ALL of them. Only report completion when the task is truly finished."""
                        
                        task_with_id = f"{task}\n\n{code_of_conduct}\n\n{user_discovery}\n\n{clarification_instructions}\n\n{task_completion}"
                        current_task = task_with_id
                        
                        # Execute task - agent will request clarification if needed
                        clarification_rounds = 0
                        max_clarification_rounds = 3
                        
                        while clarification_rounds <= max_clarification_rounds:
                            messages = [HumanMessage(content=current_task)]
                            
                            # Add timeout to prevent hanging - reduced for faster execution
                            try:
                                result = await asyncio.wait_for(
                                    agent.ainvoke({"messages": messages}),
                                    timeout=180.0  # 3 minute timeout - allows time for clarification and MCP operations
                                )
                            except asyncio.TimeoutError:
                                output_parts.append("Error: Agent execution timed out after 1 minute")
                                raise TimeoutError("Langchain agent execution timed out")
                            
                            # Collect agent output
                            agent_output = ""
                            if "messages" in result:
                                for msg in result["messages"]:
                                    if hasattr(msg, 'content'):
                                        content = str(msg.content)
                                        output_parts.append(content)
                                        agent_output += content
                                    else:
                                        output_parts.append(str(msg))
                                        agent_output += str(msg)
                            else:
                                output_parts.append(str(result))
                                agent_output = str(result)
                            
                            # Verify message was actually sent by checking for success indicators
                            if "chatPostMessage" in agent_output.lower() or "chatpostmessage" in agent_output.lower():
                                # Check if we got a successful response
                                import json
                                try:
                                    # Look for JSON response with "ok":true
                                    if '"ok":true' in agent_output or '"ok": true' in agent_output:
                                        # Try to extract channel and timestamp
                                        if self.target_identifier and f'"{self.target_identifier}' in agent_output:
                                            output_parts.append(f"\n✅ Message verification: API returned success for target {self.target_identifier}")
                                        elif '"ok":true' in agent_output or '"ok": true' in agent_output:
                                            output_parts.append(f"\n✅ Message verification: API returned success")
                                        else:
                                            output_parts.append(f"\n⚠️  Message verification: API returned success but target may differ. Check output manually.")
                                    else:
                                        output_parts.append(f"\n⚠️  Message verification: API response may indicate failure. Check output above.")
                                except:
                                    pass
                            
                            # Check if agent requested clarification
                            # Only handle clarification if agent actually requested it
                            needs_clarification = False
                            clarification_match = ""
                            
                            # Look for ACTUAL clarification requests, not our instruction examples
                            # Instruction text contains: "CLARIFICATION_NEEDED: [your question]"
                            # Real requests look like: CLARIFICATION_NEEDED: What channel should I use?
                            import re
                            # Match CLARIFICATION_NEEDED: at start of line or after newline, NOT inside quotes
                            clarification_pattern = r'(?:^|\n)\s*CLARIFICATION_NEEDED:\s*([^\n"]+)'
                            clarification_matches = re.findall(clarification_pattern, agent_output)
                            
                            if DEBUG_MODE:
                                console.print(f"[magenta]DEBUG [Langchain] Checking for clarification requests[/magenta]")
                                console.print(f"[magenta]DEBUG [Langchain] Pattern matches: {clarification_matches}[/magenta]")
                            
                            if clarification_matches and self.interactive_prompt:
                                # Get the last match (most recent request)
                                clarification_match = clarification_matches[-1].strip()
                                if DEBUG_MODE:
                                    console.print(f"[magenta]DEBUG [Langchain] Clarification text: {repr(clarification_match)}[/magenta]")
                                    console.print(f"[magenta]DEBUG [Langchain] len={len(clarification_match)}, has_alpha={any(c.isalpha() for c in clarification_match)}[/magenta]")
                                # Only consider it a valid clarification if there's actual content
                                if clarification_match and len(clarification_match) > 5 and any(c.isalpha() for c in clarification_match):
                                    needs_clarification = True
                                    if DEBUG_MODE:
                                        console.print(f"[magenta]DEBUG [Langchain] Valid clarification - will show prompt[/magenta]")
                                elif DEBUG_MODE:
                                    console.print(f"[magenta]DEBUG [Langchain] Invalid clarification - skipping prompt[/magenta]")
                            
                            if needs_clarification:
                                # Show agent's question and get user response
                                console.print()  # Add spacing
                                console.print(Panel(
                                    f"[bold cyan]🤖 Langchain Agent needs clarification:[/bold cyan]\n\n{clarification_match}",
                                    title="Clarification Request",
                                    border_style="green"
                                ))
                                console.print()
                                
                                # Simple input prompt - cursor appears right after this text
                                console.print("[bold yellow]Your response: [/bold yellow]", end="")
                                sys.stdout.flush()
                                
                                try:
                                    # Check if interactive_prompt is async or sync
                                    # Try to call it and check if result is a coroutine
                                    prompt_result = self.interactive_prompt("")
                                    if inspect.iscoroutine(prompt_result):
                                        # It's async - await it
                                        user_response = await prompt_result
                                    elif inspect.iscoroutinefunction(self.interactive_prompt):
                                        # Function is async but we got a coroutine - await it
                                        user_response = await prompt_result
                                    else:
                                        # It's sync - use the result directly
                                        user_response = prompt_result
                                    
                                    # Ensure user_response is a string (handle coroutine objects that weren't awaited)
                                    if inspect.iscoroutine(user_response):
                                        console.print("[red]ERROR: Got coroutine object instead of string! This is a bug.[/red]")
                                        user_response = ""
                                    if user_response is None:
                                        user_response = ""
                                    user_response = str(user_response)
                                    
                                    if user_response and user_response.strip():
                                        # Add clarification to task in a clear format that the agent will understand
                                        # Make it explicit so the agent doesn't ask again
                                        clarification_text = user_response.strip()
                                        # Format clarification to be very explicit and prevent looping
                                        current_task = f"""{current_task}

CRITICAL USER CLARIFICATION - USE THIS INFORMATION NOW:
{clarification_text}

IMPORTANT: The user has provided the above clarification. You MUST use this information to complete the task. Do NOT ask for clarification again on this topic. If the clarification mentions a channel, use that channel. If it mentions a message, use that message. Proceed with execution using this information."""
                                        clarification_rounds += 1
                                        agent_output = ""  # Reset for next round
                                        console.print()  # New line after input
                                        console.print(f"[green]✓ Received: {clarification_text}[/green]")
                                        console.print("[dim]Continuing with clarification...[/dim]\n")
                                        # Continue loop to re-execute with clarification
                                        continue
                                    else:
                                        # User pressed Enter - proceed anyway
                                        console.print("[yellow]No response provided, proceeding anyway...[/yellow]\n")
                                        break
                                except (EOFError, KeyboardInterrupt):
                                    console.print("\n[yellow]Clarification cancelled, proceeding...[/yellow]\n")
                                    break
                                except Exception as e:
                                    console.print(f"[red]Error getting clarification: {e}[/red]")
                                    console.print("[yellow]Proceeding without clarification...[/yellow]\n")
                                    break
                            
                            # No clarification needed or max rounds reached - break
                            break
                        
                        if exec_step:
                            exec_step.finish()
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
                
                # Add timeout to MCP connection to prevent hanging (300+ second issue)
                # Increased timeout to allow for clarification prompts (2 minutes) + MCP connection time
                try:
                    await asyncio.wait_for(
                        run_agent_session(config, on_ready, storage=storage),
                        timeout=300.0  # 5 minute timeout for entire MCP connection + setup + clarification (allows 2 min for clarification)
                    )
                except asyncio.TimeoutError:
                    step.finish()
                    self._update_progress("Langchain Agent", "❌ MCP connection timed out")
                    return AgentResult(
                        agent_name="Langchain Agent",
                        success=False,
                        output="",
                        error="MCP connection timed out after 3 minutes. Server may be unresponsive or OAuth flow took too long.",
                        timing_steps=timing_steps
                    )
                except Exception as e:
                    step.finish()
                    error_msg = str(e)
                    # Don't show cancel scope errors to user - they're internal
                    if "cancel scope" in error_msg.lower():
                        error_msg = "MCP connection error (internal)"
                    self._update_progress("Langchain Agent", f"❌ Error: {error_msg[:50]}")
                    return AgentResult(
                        agent_name="Langchain Agent",
                        success=False,
                        output="",
                        error=error_msg,
                        timing_steps=timing_steps
                    )
                if timing_steps and not timing_steps[-1].end_time:
                    timing_steps[-1].finish()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                # Calculate KPIs with better detection
                output_str = "\n".join(output_parts)
                output_lower = output_str.lower()
                
                # Better tool call detection
                tool_calls_count = (
                    output_str.count("tool") + 
                    output_str.count("mcp") +
                    output_str.count("chatPostMessage") +
                    output_str.count("conversationsHistory") +
                    output_str.count("searchMessages")
                )
                
                # Better message sent detection
                message_sent = (
                    "message" in output_lower and 
                    ("sent" in output_lower or "posted" in output_lower or "delivered" in output_lower or "success" in output_lower) and
                    ("error" not in output_lower or "failed" not in output_lower)
                ) or "chatpostmessage" in output_lower
                
                # Better target reached detection - generic
                target_reached = (
                    (self.target_identifier and self.target_identifier in output_str) or
                    "channel" in output_lower or 
                    "dm" in output_lower or
                    "direct message" in output_lower or
                    "target" in output_lower
                )
                
                safety_followed = "public" not in output_lower and "general" not in output_lower
                
                # Generate failure explanations
                message_failure_reason = None
                target_failure_reason = None
                tool_failure_details = []
                
                if not message_sent:
                    if tool_calls_count == 0:
                        message_failure_reason = "No tools were called. Agent may not have attempted to send message."
                    elif "error" in output_lower or "failed" in output_lower:
                        error_keywords = ["error", "failed", "exception", "unauthorized", "forbidden", "not found"]
                        for keyword in error_keywords:
                            if keyword in output_lower:
                                idx = output_lower.find(keyword)
                                snippet = output_str[max(0, idx-50):idx+100]
                                message_failure_reason = f"Error detected: {snippet[:100]}..."
                                break
                        if not message_failure_reason:
                            message_failure_reason = "Message sending failed (error detected in output)."
                    else:
                        message_failure_reason = "Message sending not confirmed. Check agent output for details."
                
                if not target_reached:
                    if self.target_identifier and self.target_identifier not in output_str:
                        target_failure_reason = f"Target identifier {self.target_identifier} not referenced. Agent may not have used correct target."
                    else:
                        target_failure_reason = "Target reached status unclear. Check agent output."
                
                if tool_calls_count == 0:
                    tool_failure_details.append("No tool calls detected. Agent may not have executed required actions.")
                
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
                            safety_constraints_followed=safety_followed,
                            message_failure_reason=message_failure_reason,
                            target_failure_reason=target_failure_reason,
                            tool_failure_details=tool_failure_details
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
                # Import from openai_agent directory - use absolute import to avoid conflicts
                import importlib.util
                mcp_config_path = os.path.join(openai_path, "mcp_config.py")
                spec = importlib.util.spec_from_file_location("openai_mcp_config", mcp_config_path)
                openai_mcp_config = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(openai_mcp_config)
                build_mcp_server = openai_mcp_config.build_mcp_server
                
                # Import auth and agents normally
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
                
                # Connect with timeout to prevent hanging
                # Add detailed error logging to diagnose ClientRequest timeout
                try:
                    # Enable detailed logging for MCP and httpx to trace the 5.0s timeout
                    import logging
                    mcp_logger = logging.getLogger("agents.mcp")
                    httpx_logger = logging.getLogger("httpx")
                    mcp_logger.setLevel(logging.DEBUG)
                    httpx_logger.setLevel(logging.DEBUG)
                    
                    self._update_progress("OpenAI Agent", "Connecting to MCP server (this may take a moment)...")
                    console.print("[dim]🔍 DEBUG: About to call mcp_server.connect()...[/dim]")
                    console.print(f"[dim]   MCP URL: {self.mcp_url}[/dim]")
                    console.print(f"[dim]   Params timeout: {mcp_server._params.get('timeout', 'N/A') if hasattr(mcp_server, '_params') else 'N/A'}[/dim]")
                    
                    # Wrap connect() with detailed error handling
                    try:
                        console.print("[dim]   Calling mcp_server.connect() - watch for httpx DEBUG logs...[/dim]")
                        console.print("[dim]   If you see 'FACTORY CALL #' in logs, the factory is being used[/dim]")
                        console.print("[dim]   If you see 5.0s timeout, the factory may not be called[/dim]")
                        console.print()
                        
                        await asyncio.wait_for(
                            mcp_server.connect(),
                            timeout=120.0  # Increased to 2 minutes to allow for slow initial connection
                        )
                        self._update_progress("OpenAI Agent", "✓ MCP connection established")
                        console.print("[green]✓ Connection successful - no timeout errors[/green]")
                    except Exception as connect_error:
                        # Log the exact error and stack trace
                        import traceback
                        error_trace = traceback.format_exc()
                        error_str = str(connect_error)
                        
                        console.print()
                        console.print(f"[red]❌ Error during mcp_server.connect():[/red]")
                        console.print(f"[red]{error_str}[/red]")
                        
                        # Check if it's the 5.0 second timeout
                        if "5.0" in error_str or "ClientRequest" in error_str:
                            console.print()
                            console.print("[yellow]⚠️  DIAGNOSIS: 5.0 SECOND TIMEOUT DETECTED[/yellow]")
                            console.print("[yellow]=" * 60 + "[/yellow]")
                            console.print("[yellow]Root Cause Analysis:[/yellow]")
                            console.print("[yellow]  1. The error 'Timed out while waiting for response to ClientRequest. Waited 5.0 seconds'[/yellow]")
                            console.print("[yellow]     indicates httpx is using its default 5.0 second timeout[/yellow]")
                            console.print()
                            console.print("[yellow]  2. This suggests:[/yellow]")
                            console.print("[yellow]     • httpx_client_factory may not be called by the SDK[/yellow]")
                            console.print("[yellow]     • OR the SDK creates httpx clients before calling the factory[/yellow]")
                            console.print("[yellow]     • OR there's a request made without using our custom client[/yellow]")
                            console.print()
                            console.print("[yellow]  3. Check the logs above for:[/yellow]")
                            console.print("[yellow]     • 'FACTORY CALL #' messages - confirms factory is called[/yellow]")
                            console.print("[yellow]     • httpx DEBUG logs showing actual timeout values used[/yellow]")
                            console.print("[yellow]     • Any requests made with 5.0s timeout[/yellow]")
                            console.print()
                            console.print("[yellow]  4. Possible solutions:[/yellow]")
                            console.print("[yellow]     • Verify httpx_client_factory parameter name is correct[/yellow]")
                            console.print("[yellow]     • Check if SDK version supports httpx_client_factory[/yellow]")
                            console.print("[yellow]     • May need to patch httpx default timeout globally[/yellow]")
                            console.print("[yellow]=" * 60 + "[/yellow]")
                        
                        console.print()
                        console.print(f"[dim]Full traceback:[/dim]")
                        console.print(f"[dim]{error_trace}[/dim]")
                        
                        raise  # Re-raise to be caught by outer handler
                except asyncio.TimeoutError:
                    step.finish()
                    self._update_progress("OpenAI Agent", "❌ MCP connection timed out")
                    return AgentResult(
                        agent_name="OpenAI Agent",
                        success=False,
                        output="",
                        error="MCP connection timed out after 2 minutes. Server may be unresponsive or initial handshake is slow.",
                        timing_steps=timing_steps
                    )
                except RuntimeError as e:
                    # Handle cancel scope errors gracefully (from anyio)
                    error_msg = str(e)
                    if "cancel scope" in error_msg.lower():
                        # This is expected when generator is closed - ignore it and continue
                        # Connection may have succeeded before the error, continue
                        pass
                    else:
                        step.finish()
                        # Log full error for debugging
                        import traceback
                        error_details = traceback.format_exc()
                        console.print(f"[dim]Full error trace: {error_details}[/dim]")
                        self._update_progress("OpenAI Agent", f"❌ Connection error: {error_msg[:50]}")
                        return AgentResult(
                            agent_name="OpenAI Agent",
                            success=False,
                            output="",
                            error=f"{error_msg} (Full trace in logs)",
                            timing_steps=timing_steps
                        )
                except Exception as e:
                    step.finish()
                    error_msg = str(e)
                    # Log full error for debugging ClientRequest timeout
                    import traceback
                    error_details = traceback.format_exc()
                    console.print(f"[dim]Full error trace: {error_details}[/dim]")
                    
                    # Check if it's the specific ClientRequest timeout
                    if "ClientRequest" in error_msg and "5.0" in error_msg:
                        console.print("[yellow]⚠️  ClientRequest timeout detected - this suggests the httpx client factory may not be applied correctly[/yellow]")
                        console.print("[yellow]   The default 5.0 second timeout is being used instead of our custom timeout[/yellow]")
                    
                    if "cancel scope" in error_msg.lower():
                        # This is expected when generator is closed - ignore it and continue
                        pass
                    else:
                        self._update_progress("OpenAI Agent", f"❌ Connection error: {error_msg[:50]}")
                        return AgentResult(
                            agent_name="OpenAI Agent",
                            success=False,
                            output="",
                            error=f"{error_msg} (Check logs for full trace)",
                            timing_steps=timing_steps
                        )
                step.finish()
                
                step = TimingStep("Agent Initialization", datetime.now())
                timing_steps.append(step)
                self._update_progress("OpenAI Agent", "Initializing OpenAI Agent...")
                
                # Get model from instance, env var, or default
                model = self.openai_model if self.openai_model else os.environ.get("OPENAI_MODEL", "gpt-4o")
                
                # Build concise instructions for the agent (shortened to avoid context length issues)
                if self.target_identifier:
                    agent_instructions = f"""You are an AI agent with MCP server tools. You MUST use tools to complete tasks.

TARGET: Use channel/user ID '{self.target_identifier}' directly. Don't search.

IMPORTANT: You MUST call chatPostMessage with channel='{self.target_identifier}' to send messages.
Do NOT just say you did something - actually call the tool!

Example: To say hello, call chatPostMessage(channel='{self.target_identifier}', text='Hello!')"""
                else:
                    agent_instructions = """You are an AI agent with MCP server tools. You MUST use tools.

SAFETY: Only do what's explicitly requested.

USER DISCOVERY: Find user/channel info using usersList or conversationsList before messaging.

CLARIFICATION: If unclear, output: "CLARIFICATION_NEEDED: [question]"

IMPORTANT: Actually call tools - don't just describe what you would do."""
                
                # Set temperature if provided
                agent_kwargs = {
                    "name": "OpenAI Agent",
                    "instructions": agent_instructions,
                    "model": model,
                    "mcp_servers": [mcp_server]
                }
                # Temperature control (if supported by OpenAI Agents SDK)
                if self.temperature is not None:
                    try:
                        agent_kwargs["temperature"] = self.temperature
                    except:
                        pass  # Ignore if not supported
                agent = Agent(**agent_kwargs)
                step.finish()
                
                step = TimingStep("Task Execution", datetime.now())
                timing_steps.append(step)
                
                # Keep task minimal - instructions are already in Agent.instructions
                interpreted_task = task
                
                current_task = interpreted_task
                
                # Execute task - agent will request clarification if needed
                self._update_progress("OpenAI Agent", "Interpreting and executing task...")
                
                clarification_rounds = 0
                max_clarification_rounds = 3
                agent_output = ""
                
                output_parts = []  # Initialize output_parts
                while clarification_rounds <= max_clarification_rounds:
                    # Execute agent (Runner.run is synchronous, so run in thread)
                    # Note: Runner.run might be async, check and handle both cases
                    try:
                        # Try as async first with timeout
                        if inspect.iscoroutinefunction(Runner.run):
                            result = await asyncio.wait_for(
                                Runner.run(agent, current_task),
                                timeout=180.0  # 3 minute timeout for task execution
                            )
                        else:
                            result = await asyncio.wait_for(
                                asyncio.to_thread(Runner.run, agent, current_task),
                                timeout=180.0  # 3 minute timeout for task execution
                            )
                    except asyncio.TimeoutError:
                        output_parts.append("Error: Task execution timed out after 3 minutes")
                        agent_output = "\n".join(output_parts)
                        break
                    except TypeError:
                        # Fallback to thread if it's not async
                        try:
                            result = await asyncio.wait_for(
                                asyncio.to_thread(Runner.run, agent, current_task),
                                timeout=180.0  # 3 minute timeout
                            )
                        except asyncio.TimeoutError:
                            output_parts.append("Error: Task execution timed out after 3 minutes")
                            agent_output = "\n".join(output_parts)
                            break
                    except Exception as e:
                        error_msg = str(e)
                        # Handle context length errors
                        if "context_length_exceeded" in error_msg.lower() or "context window" in error_msg.lower():
                            output_parts.append("Error: Context length exceeded. Task too long. Try a shorter task or use --openai-model gpt-4-turbo")
                            agent_output = "\n".join(output_parts)
                            break
                        # Re-raise other errors
                        raise
                    
                    # Collect output
                    if hasattr(result, 'final_output') and result.final_output:
                        output = result.final_output
                        output_parts.append(output)
                        agent_output += output
                    elif hasattr(result, 'output'):
                        output = str(result.output)
                        output_parts.append(output)
                        agent_output += output
                    else:
                        output = str(result)
                        output_parts.append(output)
                        agent_output += output
                    
                    # Check if agent requested clarification
                    # Use regex to find ACTUAL requests, not our instruction examples
                    import re
                    clarification_pattern = r'(?:^|\n)\s*CLARIFICATION_NEEDED:\s*([^\n"]+)'
                    clarification_matches = re.findall(clarification_pattern, agent_output)
                    
                    if DEBUG_MODE:
                        console.print(f"[magenta]DEBUG [OpenAI] Checking for clarification requests[/magenta]")
                        console.print(f"[magenta]DEBUG [OpenAI] Pattern matches: {clarification_matches}[/magenta]")
                    
                    if clarification_matches and self.interactive_prompt:
                        clarification_match = clarification_matches[-1].strip()
                        if DEBUG_MODE:
                            console.print(f"[magenta]DEBUG [OpenAI] Clarification text: {repr(clarification_match)}[/magenta]")
                        # Only consider it a valid clarification if there's actual content
                        if clarification_match and len(clarification_match) > 5 and any(c.isalpha() for c in clarification_match):
                            # Show agent's question and get user response
                            console.print()  # Add spacing
                            console.print(Panel(
                                f"[bold cyan]🤖 OpenAI Agent needs clarification:[/bold cyan]\n\n{clarification_match}",
                                title="Clarification Request",
                                border_style="yellow"
                            ))
                            console.print()
                            try:
                                # Check if interactive_prompt is async or sync
                                # Try to call it and check if result is a coroutine
                                prompt_result = self.interactive_prompt("[bold yellow]Your response: [/bold yellow]")
                                if inspect.iscoroutine(prompt_result):
                                    # It's async - await it
                                    user_response = await prompt_result
                                elif inspect.iscoroutinefunction(self.interactive_prompt):
                                    # Function is async but we got a coroutine - await it
                                    user_response = await prompt_result
                                else:
                                    # It's sync - use the result directly
                                    user_response = prompt_result
                                
                                # Ensure user_response is a string (handle coroutine objects that weren't awaited)
                                if inspect.iscoroutine(user_response):
                                    console.print("[red]ERROR: Got coroutine object instead of string! This is a bug.[/red]")
                                    user_response = ""
                                if user_response is None:
                                    user_response = ""
                                user_response = str(user_response)
                                
                                if user_response and user_response.strip():
                                    # Add clarification to task in a clear format that the agent will understand
                                    # Make it explicit so the agent doesn't ask again
                                    clarification_text = user_response.strip()
                                    # Format clarification to be very explicit and prevent looping
                                    current_task = f"""{current_task}

CRITICAL USER CLARIFICATION - USE THIS INFORMATION NOW:
{clarification_text}

IMPORTANT: The user has provided the above clarification. You MUST use this information to complete the task. Do NOT ask for clarification again on this topic. If the clarification mentions a channel, use that channel. If it mentions a message, use that message. Proceed with execution using this information."""
                                    clarification_rounds += 1
                                    agent_output = ""  # Reset for next round
                                    console.print()  # New line after input
                                    console.print(f"[green]✓ Received: {clarification_text}[/green]")
                                    console.print("[dim]Continuing with clarification...[/dim]\n")
                                    # Continue loop to re-execute with clarification
                                    continue
                                else:
                                    # User pressed Enter - proceed anyway
                                    console.print("[yellow]No response provided, proceeding anyway...[/yellow]\n")
                                    break
                            except (EOFError, KeyboardInterrupt):
                                console.print("\n[yellow]Clarification cancelled, proceeding...[/yellow]\n")
                                break
                            except Exception as e:
                                console.print(f"[red]Error getting clarification: {e}[/red]")
                                console.print("[yellow]Proceeding without clarification...[/yellow]\n")
                                break
                    
                    # No clarification needed or max rounds reached - break
                    break
                
                step.finish()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                output = agent_output if agent_output else (result.final_output if result and hasattr(result, 'final_output') and result.final_output else "No output")
                
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
            error_msg = str(e)
            # Handle context length errors specifically
            if "context_length_exceeded" in error_msg.lower() or "context window" in error_msg.lower():
                error_msg = "Context length exceeded. Task or instructions too long. Try a shorter task or use a model with larger context window (e.g., gpt-4-turbo)."
            # Don't show cancel scope errors - they're internal
            elif "cancel scope" in error_msg.lower():
                error_msg = "MCP connection error (internal)"
            return AgentResult(
                agent_name="OpenAI Agent",
                success=False,
                output="",
                error=error_msg,
                execution_time=execution_time,
                timing_steps=timing_steps
            )
    
    async def run_agents(self, task: str, selected_agents: List[str]) -> List[AgentResult]:
        """Run task across selected agents."""
        results = []
        current_task = task
        
        # Check if running multiple agents (parallel) or single agent
        is_parallel = len(selected_agents) > 1
        
        if is_parallel:
            # Initialize queue system for parallel execution
            if self.input_queue is None:
                self.input_queue = asyncio.Queue()
                self.input_responses = {}
                self.input_event = asyncio.Event()
            
            # Parallel execution with round-robin input queue
            async def run_agent_with_queue(agent_name: str, agent_func, original_task: str):
                """Run agent and handle input queue requests."""
                try:
                    # Add agent to input queue system
                    if self.interactive_prompt:
                        # Agent can request input by putting itself in queue
                        async def request_input(prompt_text: str) -> str:
                            """Request user input through round-robin queue with task context."""
                            # Include original task in the queue for context
                            await self.input_queue.put((agent_name, prompt_text, original_task))
                            # Wait for response
                            while agent_name not in self.input_responses:
                                await asyncio.sleep(0.1)
                            response = self.input_responses.pop(agent_name, "")
                            return response
                        
                        # Temporarily replace interactive_prompt for this agent
                        original_prompt = self.interactive_prompt
                        self.interactive_prompt = request_input
                    
                    result = await agent_func(current_task)
                    return result
                finally:
                    if self.interactive_prompt:
                        self.interactive_prompt = original_prompt
            
            # Store original prompt for input handler (before defining closure)
            original_prompt_for_handler = self.interactive_prompt
            
            # Start input handler for round-robin queue
            async def input_handler():
                """Handle input requests in round-robin fashion."""
                while True:
                    try:
                        # Wait for input request with timeout - allow 2 minutes for clarification
                        queue_item = await asyncio.wait_for(
                            self.input_queue.get(),
                            timeout=120.0  # 2 minute timeout for user input (as requested)
                        )
                        
                        # Unpack queue item (agent_name, prompt_text, original_task)
                        if len(queue_item) == 3:
                            agent_name, prompt_text, original_task = queue_item
                        elif len(queue_item) == 2:
                            agent_name, prompt_text = queue_item
                            original_task = None
                        else:
                            # Invalid format, skip
                            self.input_queue.task_done()
                            continue
                        
                        # Get user input with context
                        try:
                            # Validate the prompt text - skip if it's empty or just punctuation
                            clean_prompt = prompt_text.strip() if prompt_text else ""
                            if DEBUG_MODE:
                                console.print(f"[magenta]DEBUG [InputHandler] Got request from {agent_name}[/magenta]")
                                console.print(f"[magenta]DEBUG [InputHandler] prompt_text: {repr(prompt_text[:100] if prompt_text and len(prompt_text) > 100 else prompt_text)}[/magenta]")
                                console.print(f"[magenta]DEBUG [InputHandler] clean_prompt: {repr(clean_prompt)}[/magenta]")
                                console.print(f"[magenta]DEBUG [InputHandler] len={len(clean_prompt)}, has_alpha={any(c.isalpha() for c in clean_prompt) if clean_prompt else False}[/magenta]")
                            if not clean_prompt or len(clean_prompt) < 5 or not any(c.isalpha() for c in clean_prompt):
                                # Invalid clarification request - skip it
                                if DEBUG_MODE:
                                    console.print(f"[magenta]DEBUG [InputHandler] SKIPPING invalid clarification[/magenta]")
                                self.input_responses[agent_name] = ""
                                self.input_queue.task_done()
                                continue
                            
                            # CRITICAL: Pause the loading screen to allow user input
                            # The Live display interferes with terminal input
                            if _loading_screen:
                                _loading_screen.pause()
                            
                            # Display the clarification request
                            console.print()
                            console.print(Panel(
                                f"[bold cyan]🤖 {agent_name} needs clarification:[/bold cyan]\n\n{clean_prompt}",
                                title="Clarification Request",
                                border_style="cyan"
                            ))
                            console.print()
                            
                            # Simple input prompt - cursor appears right after this text
                            console.print("[bold yellow]Your response: [/bold yellow]", end="")
                            sys.stdout.flush()
                            
                            # Check if original_prompt_for_handler is async or sync
                            # IMPORTANT: Use console.input() directly for better interactive support
                            try:
                                # Use console.input() which properly handles interactive terminals
                                if inspect.iscoroutinefunction(original_prompt_for_handler):
                                    user_input = await original_prompt_for_handler("")
                                else:
                                    # For sync functions, run in thread to avoid blocking
                                    # But ensure we're using console.input() which handles terminals properly
                                    user_input = await asyncio.to_thread(
                                        original_prompt_for_handler,
                                        ""  # Empty string since we already printed the prompt
                                    )
                            except Exception as e:
                                # Final fallback: read from stdin directly
                                console.print(f"[yellow]⚠️  Using stdin fallback: {e}[/yellow]")
                                try:
                                    # Flush output to ensure prompt is visible
                                    sys.stdout.flush()
                                    user_input = await asyncio.to_thread(sys.stdin.readline)
                                    if user_input:
                                        user_input = user_input.strip()
                                    else:
                                        user_input = ""
                                except Exception:
                                    user_input = ""
                            
                            # Ensure we have a string
                            if user_input is None:
                                user_input = ""
                            user_input = str(user_input).strip()
                            
                            # If still empty after waiting, log it
                            if not user_input:
                                console.print("[yellow]No response provided, proceeding anyway...[/yellow]\n")
                            else:
                                console.print(f"[green]✓ Received: {user_input}[/green]\n")
                            
                            self.input_responses[agent_name] = user_input
                            
                            # Resume the loading screen after getting input
                            if _loading_screen:
                                _loading_screen.resume()
                        except (EOFError, KeyboardInterrupt):
                            console.print("\n[yellow]Clarification cancelled, proceeding...[/yellow]\n")
                            self.input_responses[agent_name] = ""
                            # Resume the loading screen
                            if _loading_screen:
                                _loading_screen.resume()
                        except Exception as e:
                            # Log error but still set empty response to unblock agent
                            console.print(f"[yellow]Warning: Error getting input for {agent_name}: {e}[/yellow]")
                            self.input_responses[agent_name] = ""
                            # Resume the loading screen
                            if _loading_screen:
                                _loading_screen.resume()
                        
                        self.input_queue.task_done()
                    except asyncio.TimeoutError:
                        # Continue checking for input requests
                        continue
            
            # Start input handler
            input_handler_task = None
            if self.interactive_prompt:
                input_handler_task = asyncio.create_task(input_handler())
            
            # Run all agents in parallel
            tasks = []
            if "anthropic" in selected_agents:
                tasks.append(("Anthropic Agent", self.run_anthropic_agent))
            if "langchain" in selected_agents:
                tasks.append(("Langchain Agent", self.run_langchain_agent))
            if "openai" in selected_agents:
                tasks.append(("OpenAI Agent", self.run_openai_agent))
            
            # Execute all in parallel (pass original task for context)
            agent_tasks = [run_agent_with_queue(name, func, task) for name, func in tasks]
            agent_results = await asyncio.gather(*agent_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(agent_results):
                if isinstance(result, Exception):
                    # Create error result
                    error_result = AgentResult(
                        agent_name=tasks[i][0],
                        success=False,
                        output="",
                        error=str(result),
                        execution_time=0,
                        timing_steps=[]
                    )
                    results.append(error_result)
                    self._update_progress(tasks[i][0], "❌ Failed")
                else:
                    results.append(result)
                    self._update_progress(tasks[i][0], "✅ Complete" if result.success else "❌ Failed")
            
            # Cancel input handler and clean up
            if input_handler_task:
                input_handler_task.cancel()
                try:
                    await input_handler_task
                except asyncio.CancelledError:
                    pass
            # Clear queue system
            if self.input_queue:
                while not self.input_queue.empty():
                    try:
                        self.input_queue.get_nowait()
                        self.input_queue.task_done()
                    except:
                        pass
                self.input_responses = {}
        else:
            # Single agent execution - wait for user input
            if "anthropic" in selected_agents:
                result = await self.run_anthropic_agent(current_task)
                results.append(result)
                self._update_progress("Anthropic Agent", "✅ Complete" if result.success else "❌ Failed")
            
            if "langchain" in selected_agents:
                result = await self.run_langchain_agent(current_task)
                results.append(result)
                self._update_progress("Langchain Agent", "✅ Complete" if result.success else "❌ Failed")
            
            if "openai" in selected_agents:
                result = await self.run_openai_agent(current_task)
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


async def select_agents_with_validation() -> List[str]:
    """Interactive agent selection with API key validation."""
    agents = {
        "1": ("anthropic", "Anthropic Agent (Claude Agent SDK)", "blue", "ANTHROPIC_API_KEY"),
        "2": ("langchain", "Langchain Agent (Langchain MCP)", "green", "ANTHROPIC_API_KEY or OPENAI_API_KEY"),
        "3": ("openai", "OpenAI Agent (OpenAI Agents SDK)", "yellow", "OPENAI_API_KEY")
    }
    
    # Validate API keys
    console.print("[dim]Validating API keys...[/dim]")
    validation_results = await validate_api_keys()
    
    console.print()
    console.print("[bold cyan]Select agents:[/bold cyan]")
    for key, (id, name, color, key_req) in agents.items():
        # Check if API key is available and validated
        if id == "anthropic":
            has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
            if "ANTHROPIC_API_KEY" in validation_results:
                is_valid, msg = validation_results["ANTHROPIC_API_KEY"]
                key_status = f"[green]✓[/green] {msg}" if is_valid else f"[red]✗[/red] {msg}"
            else:
                key_status = "[green]✓[/green]" if has_key else "[red]✗[/red]"
        elif id == "langchain":
            has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
            has_openai = bool(os.environ.get("OPENAI_API_KEY"))
            has_key = has_anthropic or has_openai
            # Show validation for whichever key is available
            if has_anthropic and "ANTHROPIC_API_KEY" in validation_results:
                is_valid, msg = validation_results["ANTHROPIC_API_KEY"]
                key_status = f"[green]✓[/green] {msg}" if is_valid else f"[red]✗[/red] {msg}"
            elif has_openai and "OPENAI_API_KEY" in validation_results:
                is_valid, msg = validation_results["OPENAI_API_KEY"]
                key_status = f"[green]✓[/green] {msg}" if is_valid else f"[red]✗[/red] {msg}"
            else:
                key_status = "[green]✓[/green]" if has_key else "[red]✗[/red]"
        else:  # openai
            has_key = bool(os.environ.get("OPENAI_API_KEY"))
            if "OPENAI_API_KEY" in validation_results:
                is_valid, msg = validation_results["OPENAI_API_KEY"]
                key_status = f"[green]✓[/green] {msg}" if is_valid else f"[red]✗[/red] {msg}"
            else:
                key_status = "[green]✓[/green]" if has_key else "[red]✗[/red]"
        
        console.print(f"  [{color}]{key}[/{color}]. {name} {key_status} (requires {key_req})")
    
    console.print("  [bold cyan]4. All agents[/bold cyan] (recommended for comparison)")
    console.print()
    console.print("[dim]💡 Tip: Invalid/expired keys will cause agent failures[/dim]")
    console.print()
    
    try:
        selection = console.input("[bold cyan]Choice (1-4, 'all', or comma-separated, e.g., 1,2,3): [/bold cyan]").strip()
        if not selection:
            selection = "4"  # Default to all
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]⚠️  Selection cancelled, using all agents[/yellow]")
        return ["anthropic", "langchain", "openai"]
    
    # Normalize selection - handle "all" or "4"
    if selection.lower() == "all" or selection == "4":
        # Check for missing or invalid keys
        missing = []
        invalid = []
        if not os.environ.get("ANTHROPIC_API_KEY"):
            missing.append("ANTHROPIC_API_KEY")
        elif "ANTHROPIC_API_KEY" in validation_results:
            is_valid, msg = validation_results["ANTHROPIC_API_KEY"]
            if not is_valid:
                invalid.append(f"ANTHROPIC_API_KEY: {msg}")
        
        if not os.environ.get("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY")
        elif "OPENAI_API_KEY" in validation_results:
            is_valid, msg = validation_results["OPENAI_API_KEY"]
            if not is_valid:
                invalid.append(f"OPENAI_API_KEY: {msg}")
        
        if missing:
            console.print(f"[yellow]⚠️  Warning: Missing API keys: {', '.join(missing)}[/yellow]")
        if invalid:
            console.print(f"[red]❌ Error: Invalid/expired API keys:[/red]")
            for inv in invalid:
                console.print(f"[red]   • {inv}[/red]")
        if missing or invalid:
            console.print("[yellow]   Some agents may fail. This is your responsibility.[/yellow]")
        return ["anthropic", "langchain", "openai"]
    
    selected = []
    for num in selection.split(","):
        num = num.strip()
        if num in agents:
            agent_id, agent_name, _, key_req = agents[num]
            # Warn if key missing or invalid
            if agent_id == "anthropic":
                if not os.environ.get("ANTHROPIC_API_KEY"):
                    console.print(f"[yellow]⚠️  Warning: ANTHROPIC_API_KEY not set. {agent_name} may fail.[/yellow]")
                elif "ANTHROPIC_API_KEY" in validation_results:
                    is_valid, msg = validation_results["ANTHROPIC_API_KEY"]
                    if not is_valid:
                        console.print(f"[red]❌ Error: ANTHROPIC_API_KEY is invalid/expired: {msg}[/red]")
                        console.print(f"[red]   {agent_name} will fail.[/red]")
            elif agent_id == "langchain":
                has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
                has_openai = bool(os.environ.get("OPENAI_API_KEY"))
                if not (has_anthropic or has_openai):
                    console.print(f"[yellow]⚠️  Warning: No API keys set. {agent_name} may fail.[/yellow]")
                elif has_anthropic and "ANTHROPIC_API_KEY" in validation_results:
                    is_valid, msg = validation_results["ANTHROPIC_API_KEY"]
                    if not is_valid:
                        console.print(f"[red]❌ Error: ANTHROPIC_API_KEY is invalid/expired: {msg}[/red]")
                elif has_openai and "OPENAI_API_KEY" in validation_results:
                    is_valid, msg = validation_results["OPENAI_API_KEY"]
                    if not is_valid:
                        console.print(f"[red]❌ Error: OPENAI_API_KEY is invalid/expired: {msg}[/red]")
            elif agent_id == "openai":
                if not os.environ.get("OPENAI_API_KEY"):
                    console.print(f"[yellow]⚠️  Warning: OPENAI_API_KEY not set. {agent_name} may fail.[/yellow]")
                elif "OPENAI_API_KEY" in validation_results:
                    is_valid, msg = validation_results["OPENAI_API_KEY"]
                    if not is_valid:
                        console.print(f"[red]❌ Error: OPENAI_API_KEY is invalid/expired: {msg}[/red]")
                        console.print(f"[red]   {agent_name} will fail.[/red]")
            selected.append(agent_id)
    
    if not selected:
        console.print("[yellow]⚠️  No valid agents selected. Using all agents.[/yellow]")
        return ["anthropic", "langchain", "openai"]
    
    return selected


# Keep old select_agents for backward compatibility, but it's now deprecated
# Use select_agents_with_validation() instead
def select_agents() -> List[str]:
    """Deprecated: Use select_agents_with_validation() for API key validation."""
    # Fallback to basic selection without validation
    agents = {
        "1": ("anthropic", "Anthropic Agent (Claude Agent SDK)", "blue", "ANTHROPIC_API_KEY"),
        "2": ("langchain", "Langchain Agent (Langchain MCP)", "green", "ANTHROPIC_API_KEY or OPENAI_API_KEY"),
        "3": ("openai", "OpenAI Agent (OpenAI Agents SDK)", "yellow", "OPENAI_API_KEY")
    }
    
    console.print("[bold cyan]Select agents:[/bold cyan]")
    for key, (id, name, color, key_req) in agents.items():
        if id == "anthropic":
            has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        elif id == "langchain":
            has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))
        else:
            has_key = bool(os.environ.get("OPENAI_API_KEY"))
        key_status = "[green]✓[/green]" if has_key else "[red]✗[/red]"
        console.print(f"  [{color}]{key}[/{color}]. {name} {key_status} (requires {key_req})")
    
    console.print("  4. All agents")
    console.print()
    
    try:
        selection = console.input("[bold cyan]Choice (1-4 or comma-separated): [/bold cyan]").strip()
        if not selection or selection == "4" or selection.lower() == "all":
            return ["anthropic", "langchain", "openai"]
    except (EOFError, KeyboardInterrupt):
        return ["anthropic", "langchain", "openai"]
    
    selected = []
    for num in selection.split(","):
        num = num.strip()
        if num in agents:
            selected.append(agents[num][0])
    
    return selected if selected else ["anthropic", "langchain", "openai"]


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


def display_results(results: List[AgentResult], task: str, mcp_url: str, mcp_capabilities: Optional[Dict[str, Any]] = None):
    """Display results in a nice format with dynamic KPIs based on MCP server capabilities."""
    console.print()
    console.print("╔══════════════════════════════════════════════════════════╗", style="bold green")
    console.print("║  📊 Execution Results                                   ║", style="bold green")
    console.print("╚══════════════════════════════════════════════════════════╝", style="bold green")
    console.print()
    
    # Discover MCP capabilities if not provided (for dynamic KPI generation)
    if mcp_capabilities is None:
        mcp_capabilities = {}
    
    # Determine success metrics based on MCP server type
    server_type = "generic"
    if "slack" in mcp_url.lower() or mcp_capabilities.get("messaging", False):
        server_type = "slack"
    elif "gitlab" in mcp_url.lower() or mcp_capabilities.get("git", False):
        server_type = "gitlab"
    elif "salesforce" in mcp_url.lower() or mcp_capabilities.get("crm", False):
        server_type = "salesforce"
    
    # Define success metrics per server type
    success_metrics = {
        "slack": {"primary": "Message Sent"},
        "gitlab": {"primary": "Operation Completed"},
        "salesforce": {"primary": "Record Created/Updated"},
        "generic": {"primary": "Tool Calls Executed"}
    }
    
    metrics = success_metrics.get(server_type, success_metrics["generic"])
    
    # Summary table with KPIs
    table = Table(title="Execution Summary", box=box.ROUNDED)
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Time", justify="right", style="dim")
    table.add_column("Tools", justify="center", style="dim")
    table.add_column(metrics["primary"], justify="center")
    table.add_column("Safety", justify="center")
    table.add_column("Error", style="red")

    for result in results:
        status = "✅ Success" if result.success else "❌ Failed"
        status_style = "green" if result.success else "red"
        time_str = f"{result.execution_time:.2f}s"
        tools_str = f"{result.tool_calls_successful}/{result.tool_calls_count}" if result.tool_calls_count > 0 else "N/A"
        
        # Dynamic success metric based on server type
        if server_type == "slack":
            primary_metric = "✅" if result.message_sent else "❌"
        elif server_type in ["gitlab", "salesforce"]:
            primary_metric = "✅" if result.tool_calls_count > 0 and result.success else "❌"
        else:  # generic
            primary_metric = "✅" if result.tool_calls_count > 0 else "❌"
        
        safety_str = "✅" if result.safety_constraints_followed else "⚠️"
        error_str = result.error[:50] + "..." if result.error and len(result.error) > 50 else (result.error or "")

        table.add_row(
            result.agent_name,
            f"[{status_style}]{status}[/{status_style}]",
            time_str,
            tools_str,
            primary_metric,
            safety_str,
            error_str
        )

    console.print(table)
    console.print()
    
    # Define success metrics per server type (expanded)
    success_metrics = {
        "slack": {
            "primary": "Message Sent",
            "secondary": "Target Reached",
            "description": "Success = message delivered to target channel"
        },
        "gitlab": {
            "primary": "Operation Completed",
            "secondary": "Target Reached",
            "description": "Success = operation completed (commit, issue, MR, etc.)"
        },
        "salesforce": {
            "primary": "Record Created/Updated",
            "secondary": "Target Reached",
            "description": "Success = record created/updated successfully"
        },
        "generic": {
            "primary": "Tool Calls Executed",
            "secondary": "Operation Completed",
            "description": "Success = tools called and operations completed"
        }
    }
    
    metrics = success_metrics.get(server_type, success_metrics["generic"])
    
    # Dynamic KPI Summary Table based on server capabilities
    kpi_title = f"Key Performance Indicators (KPIs) - {server_type.upper()} Server"
    kpi_table = Table(title=kpi_title, box=box.ROUNDED)
    kpi_table.add_column("Agent", style="cyan")
    kpi_table.add_column("Tool Calls", justify="center")
    kpi_table.add_column("Success Rate", justify="center")
    kpi_table.add_column(metrics["primary"], justify="center")
    kpi_table.add_column(metrics["secondary"], justify="center")
    kpi_table.add_column("Safety Followed", justify="center")
    
    console.print(f"[dim]{metrics['description']}[/dim]")
    console.print()
    
    for result in results:
        success_rate = f"{(result.tool_calls_successful/result.tool_calls_count*100):.1f}%" if result.tool_calls_count > 0 else "N/A"
        
        # Dynamic primary metric based on server type
        if server_type == "slack":
            if result.message_sent:
                primary = "[green]✅ Yes[/green]"
            else:
                reason = result.message_failure_reason or "Unknown reason"
                primary = f"[red]❌ No[/red]\n[dim]{reason[:60]}...[/dim]" if len(reason) > 60 else f"[red]❌ No[/red]\n[dim]{reason}[/dim]"
        elif server_type == "gitlab":
            if result.tool_calls_count > 0 and result.success:
                primary = "[green]✅ Yes[/green]"
            else:
                reason = result.tool_failure_details[0] if result.tool_failure_details else "No operations completed"
                primary = f"[red]❌ No[/red]\n[dim]{reason[:60]}...[/dim]" if len(reason) > 60 else f"[red]❌ No[/red]\n[dim]{reason}[/dim]"
        elif server_type == "salesforce":
            if result.tool_calls_count > 0 and result.success:
                primary = "[green]✅ Yes[/green]"
            else:
                reason = result.tool_failure_details[0] if result.tool_failure_details else "No records created/updated"
                primary = f"[red]❌ No[/red]\n[dim]{reason[:60]}...[/dim]" if len(reason) > 60 else f"[red]❌ No[/red]\n[dim]{reason}[/dim]"
        else:  # generic
            if result.tool_calls_count > 0:
                primary = "[green]✅ Yes[/green]"
            else:
                reason = result.tool_failure_details[0] if result.tool_failure_details else "No tools called"
                primary = f"[red]❌ No[/red]\n[dim]{reason[:60]}...[/dim]" if len(reason) > 60 else f"[red]❌ No[/red]\n[dim]{reason}[/dim]"
        
        # Secondary metric (target reached for all)
        if result.target_reached:
            secondary = "[green]✅ Yes[/green]"
        else:
            reason = result.target_failure_reason or "Unknown reason"
            secondary = f"[red]❌ No[/red]\n[dim]{reason[:60]}...[/dim]" if len(reason) > 60 else f"[red]❌ No[/red]\n[dim]{reason}[/dim]"
        
        safety_followed = "[green]✅ Yes[/green]" if result.safety_constraints_followed else "[yellow]⚠️ No[/yellow]"
        kpi_table.add_row(
            result.agent_name,
            f"{result.tool_calls_count}",
            success_rate,
            primary,
            secondary,
            safety_followed
        )
    
    console.print(kpi_table)
    console.print()
    
    # Helper function to clean agent output (remove instruction blocks)
    def clean_output(output: str) -> str:
        """Remove instruction blocks from output, keeping only agent response."""
        if not output:
            return output
        
        # Look for the actual agent response - usually after tool results
        # Find the last significant content
        import re
        
        # Try to find the final summary after tool execution
        patterns = [
            r"Perfect!.*$",  # "Perfect! I've successfully..."
            r"Successfully.*$",  # "Successfully sent..."
            r"I've successfully.*$",  # "I've successfully..."
            r"✅ Message verification.*$",  # Verification message
            r"Here's a joke.*$",  # Direct response
            r"Hello!.*$",  # Greeting
        ]
        
        # Try each pattern to find a clean ending
        for pattern in patterns:
            match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
            if match:
                result = match.group(0).strip()
                # Don't return if too short
                if len(result) > 20:
                    return result
        
        # Fallback: Remove common instruction prefixes
        skip_markers = [
            'CODE OF CONDUCT', 'PRINCIPLE OF', 'TARGET CHANNEL/USER',
            'CLARIFICATION', 'CRITICAL TASK', 'MCP SERVER DEMONSTRATION',
            'USER DISCOVERY', 'you MUST', 'Do NOT', 'IMPORTANT:',
            'For messaging:', 'Execute the task', 'Attempt to call'
        ]
        
        lines = output.split('\n')
        clean_lines = []
        in_instructions = False
        
        for line in lines:
            # Check if this line is part of instructions
            is_instruction = any(marker in line for marker in skip_markers)
            
            # Skip bullet points that look like instructions
            if line.strip().startswith('•') and any(word in line.lower() for word in ['must', 'should', 'call', 'execute', 'channel']):
                is_instruction = True
            
            if is_instruction:
                in_instructions = True
                continue
            
            # Keep lines that look like actual responses
            if any(marker in line for marker in ["I'll", "I've", "Perfect", "Successfully", "✅", "Hello", "joke", "sent", "delivered"]):
                in_instructions = False
            
            if not in_instructions:
                clean_lines.append(line)
        
        cleaned = '\n'.join(clean_lines).strip()
        return cleaned if cleaned else output[:300] + "..." if len(output) > 300 else output
    
    # Detailed results
    for result in results:
        if result.success:
            cleaned_output = clean_output(result.output)
            console.print(Panel(
                Markdown(cleaned_output) if cleaned_output else "[dim]No output[/dim]",
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
        help="MCP server URL (e.g., https://server.com/mcp). If not provided, will prompt in interactive mode."
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
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Temperature for model generation (0.0-2.0, default: model default)"
    )
    parser.add_argument(
        "--openai-model",
        dest="openai_model",
        help="OpenAI model to use (e.g., gpt-4o, gpt-4o-mini, gpt-4-turbo). Overrides OPENAI_MODEL env var."
    )
    parser.add_argument(
        "--target-channel",
        dest="target_channel",
        help="Target channel/user ID for messaging (e.g., D025N5FN3RT for Slack DM). Agents will use this directly instead of searching."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with verbose logging for clarification detection"
    )
    
    args = parser.parse_args()
    
    # Store debug mode globally for clarification debugging
    global DEBUG_MODE
    DEBUG_MODE = args.debug
    if DEBUG_MODE:
        console.print("[yellow]🔍 DEBUG MODE ENABLED - verbose clarification logging[/yellow]")
    
    # Load .env file if it exists (already loaded at top, but ensure it's done)
    try:
        from dotenv import load_dotenv
        script_dir = Path(__file__).parent
        env_file = script_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)  # Don't override existing env vars
            console.print(f"[dim]📁 Loaded .env file from {env_file}[/dim]")
        else:
            # Check parent directory
            parent_env = script_dir.parent / ".env"
            if parent_env.exists():
                load_dotenv(parent_env, override=False)
                console.print(f"[dim]📁 Loaded .env file from {parent_env}[/dim]")
    except ImportError:
        pass  # python-dotenv not installed
    
    print_banner()
    
    # Quick validation check on startup (non-blocking)
    console.print("[dim]🔍 Checking API keys...[/dim]")
    try:
        validation_results = await validate_api_keys()
        if validation_results:
            console.print()
            for key_name, (is_valid, msg) in validation_results.items():
                if is_valid:
                    console.print(f"[green]✓ {key_name}: {msg}[/green]")
                else:
                    console.print(f"[red]✗ {key_name}: {msg}[/red]")
            console.print()
    except Exception as e:
        # Don't block if validation fails
        console.print(f"[dim]⚠️  Could not validate API keys: {e}[/dim]")
        console.print()
    
    # Get MCP URL - generic, works with any MCP server (MUST come before task prompt)
    mcp_url = args.mcp_url
    if not mcp_url and not args.no_interactive:
        # Prompt for MCP URL in interactive mode with guidance
        console.print()
        console.print(Panel(
            "[bold cyan]MCP Server Configuration[/bold cyan]\n\n"
            "This tool is a [bold]universal MCP interface[/bold] that works with [bold]any MCP server[/bold].\n\n"
            "[yellow]Best Practices:[/yellow]\n"
            "  • Use the full MCP endpoint URL (usually ends with /mcp)\n"
            "  • Verify the server is accessible before proceeding\n"
            "  • Set MCP_SERVER_URL environment variable to skip this prompt\n\n"
            "[dim]Note: Connection success/failure depends on your server configuration.[/dim]",
            title="Universal MCP Interface",
            border_style="cyan"
        ))
        console.print()
        console.print("[yellow]Example MCP servers:[/yellow]")
        console.print("  • Slack: https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp")
        console.print("  • Custom: https://your-mcp-server.com/mcp")
        console.print()
        # Check for default in environment
        default_url = os.environ.get("MCP_SERVER_URL")
        if default_url:
            console.print(f"[dim]💡 Found MCP_SERVER_URL in environment: {default_url}[/dim]")
            console.print(f"[dim]   Press Enter to use this, or type a different URL[/dim]")
            console.print()
        try:
            mcp_url = console.input(f"[bold cyan]MCP Server URL[/bold cyan]{f' [{default_url}]: ' if default_url else ': '}").strip()
            if not mcp_url and default_url:
                mcp_url = default_url
                console.print(f"[green]✓ Using environment default: {mcp_url}[/green]")
            elif not mcp_url:
                console.print("[red]❌ Error: MCP URL is required. Please provide a valid MCP server URL.[/red]")
                console.print("[yellow]💡 Tip: Set MCP_SERVER_URL environment variable or use --mcp-url flag[/yellow]")
                sys.exit(1)
            else:
                console.print(f"[green]✓ Using provided URL: {mcp_url}[/green]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[red]❌ Error: MCP URL input cancelled by user[/red]")
            console.print("[yellow]💡 Tip: Use --mcp-url flag or set MCP_SERVER_URL for non-interactive use[/yellow]")
            sys.exit(1)
    elif not mcp_url:
        # Try environment variable as fallback
        mcp_url = os.environ.get("MCP_SERVER_URL")
        if not mcp_url:
            console.print("[red]❌ Error: --mcp-url is required in non-interactive mode[/red]")
            console.print("[yellow]💡 Tip: Provide --mcp-url flag or set MCP_SERVER_URL environment variable[/yellow]")
            sys.exit(1)
        console.print(f"[yellow]Using MCP_SERVER_URL from environment: {mcp_url}[/yellow]")
    
    # Get task
    if args.task:
        task = args.task
    elif args.no_interactive:
        console.print("[red]Error: --no-interactive requires --task and --agents[/red]")
        sys.exit(1)
    else:
        # Interactive mode with guidance
        console.print()
        console.print(Panel(
            "[bold cyan]Task Input[/bold cyan]\n\n"
            "Enter the task you want the agents to execute using the MCP server.\n\n"
            "[yellow]Best Practices:[/yellow]\n"
            "  • Be specific about what you want done\n"
            "  • Mention which MCP tools to use if relevant\n"
            "  • Agents will automatically discover available tools\n"
            "  • Agents may ask for clarification if needed\n\n"
            "[dim]Note: Task success depends on your task clarity and MCP server capabilities.[/dim]",
            title="Task Configuration",
            border_style="cyan"
        ))
        console.print()
        console.print("[yellow]Example Tasks:[/yellow]")
        console.print("  • \"List all available tools from the MCP server\"")
        console.print("  • \"Send a message saying hello to the target channel\"")
        console.print("  • \"Search for recent messages and summarize them\"")
        console.print()
        console.print("[dim]💡 Tip: Use --task flag for non-interactive mode[/dim]")
        console.print()
        try:
            task = console.input("[bold cyan]Task: [/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[red]❌ Error: Task input cancelled by user[/red]")
            console.print("[yellow]💡 Tip: Use --task flag for non-interactive mode[/yellow]")
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
            console.print("[red]❌ Error: Not running in interactive terminal[/red]")
            console.print("[yellow]💡 Tip: Use --agents flag, or run in an interactive terminal[/yellow]")
            sys.exit(1)
        
        # Interactive agent selection with guidance and API key validation
        console.print()
        console.print(Panel(
            "[bold cyan]Agent Selection[/bold cyan]\n\n"
            "Select which AI agents to use for this task.\n\n"
            "[yellow]Available Agents:[/yellow]\n"
            "  • [bold]anthropic[/bold] - Claude (Anthropic SDK)\n"
            "  • [bold]langchain[/bold] - Langchain framework\n"
            "  • [bold]openai[/bold] - GPT (OpenAI SDK)\n\n"
            "[yellow]Best Practices:[/yellow]\n"
            "  • Select 'all' to compare agent outputs\n"
            "  • Select specific agents to test individually\n"
            "  • API keys will be validated automatically\n\n"
            "[dim]Note: Agent success depends on API key validity and MCP server compatibility.[/dim]",
            title="Agent Selection",
            border_style="cyan"
        ))
        console.print()
        try:
            selected_agents = await select_agents_with_validation()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]⚠️  Using all agents by default (user cancelled selection)[/yellow]")
            selected_agents = ["anthropic", "langchain", "openai"]
    
    # Display configuration summary with user responsibility notice
    console.print()
    console.print(Panel(
        f"[bold]Configuration Summary[/bold]\n\n"
        f"[cyan]Task:[/cyan] {task}\n"
        f"[cyan]Selected Agents:[/cyan] {', '.join(selected_agents)}\n"
        f"[cyan]MCP Server:[/cyan] {mcp_url}\n\n"
        f"[yellow]⚠️  User Responsibility:[/yellow]\n"
        f"  • Task success depends on your task clarity\n"
        f"  • Agent success depends on API key configuration\n"
        f"  • MCP connection depends on server availability\n"
        f"  • All results are based on your configuration choices\n\n"
        f"[dim]Proceeding with execution...[/dim]",
        title="Ready to Execute",
        border_style="green"
    ))
    console.print()
    
    # Extract server name for display
    try:
        from urllib.parse import urlparse
        parsed = urlparse(mcp_url)
        mcp_server_name = parsed.netloc.split('.')[0] if parsed.netloc else parsed.path.split('/')[-2] if '/' in parsed.path else "MCP Server"
    except:
        mcp_server_name = mcp_url.split('/')[-2] if '/' in mcp_url else "MCP Server"
    
    console.print(f"[dim]Connecting to MCP server: {mcp_server_name}[/dim]")
    console.print()
    
    # Persistent loading screen class
    class LoadingScreen:
        """Persistent loading screen that stays in position."""
        def __init__(self, agent_names: List[str]):
            self.agent_names = agent_names
            self.statuses = {name: "Initializing..." for name in agent_names}
            self.live = None
            self.start_time = datetime.now()
        
        def render(self):
            """Render the loading screen."""
            elapsed = (datetime.now() - self.start_time).total_seconds()
            elapsed_str = f"{elapsed:.1f}s"
            
            # Create status rows for each agent with proper spinner rendering
            rows = []
            for agent_name in self.agent_names:
                status = self.statuses.get(agent_name, "Waiting...")
                # Use spinner emoji that animates, or use a simple icon
                spinner_icon = "⏳"  # Hourglass emoji as spinner
                rows.append(f"  {spinner_icon} [bold cyan]{agent_name}:[/bold cyan] {status}")
            
            content = "\n".join(rows)
            content += f"\n\n[dim]⏱  Elapsed: {elapsed_str}[/dim]"
            
            return Panel(
                content,
                title="[bold cyan]🤖 Agent Execution[/bold cyan]",
                border_style="cyan",
                padding=(1, 2)
            )
        
        def update_status(self, agent_name: str, status: str):
            """Update status for an agent."""
            with _loading_lock:
                if agent_name in self.statuses:
                    self.statuses[agent_name] = status
                    if self.live and self.live.is_started:
                        self.live.update(self.render())
        
        def start(self):
            """Start the live display with auto-refresh for elapsed time."""
            self._stop_event = Event()
            self.live = Live(
                self.render(), 
                console=console, 
                refresh_per_second=2,  # Update every 0.5 seconds for smooth elapsed time
                vertical_overflow="visible"
            )
            self.live.start()
            # Start background thread to continuously update elapsed time
            def update_loop():
                while not self._stop_event.is_set():
                    try:
                        # Wait 0.5 seconds, or break if event is set
                        if self._stop_event.wait(0.5):
                            break
                        # Update the display with new elapsed time
                        if self.live:
                            try:
                                self.live.update(self.render())
                            except Exception:
                                break
                    except Exception:
                        break
            self._update_thread = Thread(target=update_loop, daemon=True)
            self._update_thread.start()
        
        def pause(self):
            """Pause the live display to allow user input."""
            if hasattr(self, '_stop_event'):
                self._stop_event.set()  # Stop the update thread
            if hasattr(self, '_update_thread'):
                self._update_thread.join(timeout=1.0)
            if self.live and self.live.is_started:
                self.live.stop()
                console.print()  # New line after stopping live display
        
        def resume(self):
            """Resume the live display after user input."""
            if self.live is None or not self.live.is_started:
                # Restart the live display
                self._stop_event = Event()
                self.live = Live(
                    self.render(), 
                    console=console, 
                    refresh_per_second=2,
                    vertical_overflow="visible"
                )
                self.live.start()
                # Restart update thread
                def update_loop():
                    while not self._stop_event.is_set():
                        try:
                            if self._stop_event.wait(0.5):
                                break
                            if self.live:
                                try:
                                    self.live.update(self.render())
                                except Exception:
                                    break
                        except Exception:
                            break
                self._update_thread = Thread(target=update_loop, daemon=True)
                self._update_thread.start()
        
        def stop(self):
            """Stop the live display."""
            if hasattr(self, '_stop_event'):
                self._stop_event.set()
            if hasattr(self, '_update_thread'):
                self._update_thread.join(timeout=1.0)  # Wait up to 1 second for thread to finish
            if self.live:
                self.live.stop()
                self.live = None
    
    # Initialize loading screen after we know which agents are selected
    loading_screen = None
    if is_interactive() and not args.no_interactive:
        agent_display_names = []
        if "anthropic" in selected_agents:
            agent_display_names.append("Anthropic Agent")
        if "langchain" in selected_agents:
            agent_display_names.append("Langchain Agent")
        if "openai" in selected_agents:
            agent_display_names.append("OpenAI Agent")
        
        if agent_display_names:
            loading_screen = LoadingScreen(agent_display_names)
            loading_screen.start()
            global _loading_screen
            _loading_screen = loading_screen
    
    # Progress callback that updates both console and loading screen
    def update_progress(agent_name: str, status: str):
        """Update progress display."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        # Update loading screen if available
        if loading_screen:
            loading_screen.update_status(agent_name, status)
        # Also print to console for non-interactive or as backup
        if not loading_screen or not is_interactive():
            console.print(f"[dim][{timestamp}][/dim] [cyan]{agent_name}:[/cyan] {status}")
    
    # Create interactive prompt function - ALWAYS set it (clarification requests need user input)
    # Only skip if explicitly disabled with --no-interactive flag
    def get_user_input(prompt_text: str) -> str:
        """Get user input during agent execution with context."""
        try:
            # If prompt_text is provided, print it; otherwise assume it's already printed
            if prompt_text:
                console.print()  # New line for clarity
                console.print(prompt_text)
            # Use console.input() which properly handles interactive terminals
            # This ensures typing works correctly in all modes
            return console.input()
        except (EOFError, KeyboardInterrupt):
            return ""
    
    # Always set interactive_prompt unless explicitly disabled
    interactive_prompt_fn = None
    if not args.no_interactive:
        interactive_prompt_fn = get_user_input
    
    # Get target identifier from CLI arg, environment, or use None for generic deployment
    target_identifier = None
    if hasattr(args, 'target_channel') and args.target_channel:
        target_identifier = args.target_channel
    else:
        target_identifier = os.environ.get("MCP_TARGET_IDENTIFIER", None)
    
    runner = AgentRunner(
        mcp_url=mcp_url,
        auth_header=args.auth_header, 
        progress_callback=update_progress,
        interactive_prompt=interactive_prompt_fn,
        temperature=args.temperature,
        target_identifier=target_identifier,
        openai_model=args.openai_model if hasattr(args, 'openai_model') and args.openai_model else None
    )
    
    console.print()
    if len(selected_agents) > 1:
        if not loading_screen:
            console.print("[bold]Running agents in parallel with round-robin input queue...[/bold]")
    else:
        if not loading_screen:
            console.print("[bold]Running agent (waiting for your input)...[/bold]")
    if not loading_screen:
        console.print()
    
    try:
        results = await runner.run_agents(task, selected_agents)
    finally:
        # Stop loading screen when done
        if loading_screen:
            loading_screen.stop()
            console.print()  # Add spacing after loading screen
    
    console.print()  # New line after progress updates
    
    # Display results with dynamic KPIs
    display_results(results, task, mcp_url, runner.mcp_capabilities)
    
    # Generate and save timing log
    log_content = generate_timing_log(results, task, mcp_url)
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
