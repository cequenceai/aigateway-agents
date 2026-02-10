"""
Clarification handler for agent interactions.
Pauses execution and prompts user for input via CLI.
"""

import sys
from typing import Optional, Callable

# Try to use rich if available, fallback to basic input
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


def request_clarification(
    question: str,
    timeout: int = 120,
    default: Optional[str] = None,
    validator: Optional[Callable[[str], bool]] = None
) -> str:
    """
    Request clarification from the user via CLI.
    
    This function will:
    1. Display the question in a formatted panel
    2. Wait for user input (with timeout)
    3. Validate the response if validator provided
    4. Return the user's response
    
    Args:
        question: The question to ask the user
        timeout: Maximum seconds to wait for input (default: 120)
        default: Default value if user just presses Enter
        validator: Optional function to validate the response
        
    Returns:
        The user's response string
        
    Raises:
        TimeoutError: If no input received within timeout
        ValueError: If validator rejects the response
    """
    # Display the clarification request
    if RICH_AVAILABLE:
        console.print()
        console.print(Panel(
            f"[bold yellow]❓ CLARIFICATION NEEDED[/bold yellow]\n\n{question}",
            title="Agent Request",
            border_style="yellow",
            padding=(1, 2)
        ))
        console.print()
        
        if default:
            console.print(f"[dim]Default: {default} (press Enter to use)[/dim]")
        
        console.print(f"[dim]Timeout: {timeout} seconds[/dim]")
        console.print()
    else:
        # Fallback to basic print
        print("\n" + "=" * 60)
        print("❓ CLARIFICATION NEEDED")
        print("=" * 60)
        print(question)
        print()
        if default:
            print(f"Default: {default} (press Enter to use)")
        print(f"Timeout: {timeout} seconds")
        print()
    
    # Get user input
    try:
        if RICH_AVAILABLE:
            # Use rich Prompt which handles input nicely
            response = Prompt.ask(
                "[bold green]Your response[/bold green]",
                default=default,
                timeout=timeout,
                console=console
            )
        else:
            # Fallback to basic input
            prompt_text = "Your response"
            if default:
                prompt_text += f" (default: {default})"
            prompt_text += ": "
            print(prompt_text, end="", flush=True)
            
            import select
            import sys
            
            # Simple timeout handling for basic input
            if sys.platform != "win32":
                # Unix-like systems
                ready, _, _ = select.select([sys.stdin], [], [], timeout)
                if ready:
                    response = input().strip()
                else:
                    raise TimeoutError(f"Input timeout after {timeout} seconds")
            else:
                # Windows - no timeout support without additional libraries
                response = input().strip()
            
            if not response and default:
                response = default
        
        # Validate if validator provided
        if validator and not validator(response):
            if RICH_AVAILABLE:
                console.print("[red]❌ Invalid response. Please try again.[/red]")
            else:
                print("❌ Invalid response. Please try again.")
            # Recursively retry (but only once to avoid infinite loops)
            return request_clarification(question, timeout=timeout, default=default, validator=validator)
        
        if RICH_AVAILABLE:
            console.print(f"[green]✓ Response received: {response[:100]}...[/green]" if len(response) > 100 else f"[green]✓ Response received[/green]")
            console.print()
        else:
            print(f"✓ Response received: {response[:100]}..." if len(response) > 100 else "✓ Response received")
            print()
        
        return response
        
    except KeyboardInterrupt:
        if RICH_AVAILABLE:
            console.print("\n[yellow]⚠️  Input cancelled by user[/yellow]")
            if default:
                console.print(f"[dim]Using default: {default}[/dim]")
        else:
            print("\n⚠️  Input cancelled by user")
            if default:
                print(f"Using default: {default}")
        if default:
            return default
        raise
    except Exception as e:
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            if RICH_AVAILABLE:
                console.print(f"\n[yellow]⚠️  Input timeout after {timeout} seconds[/yellow]")
                if default:
                    console.print(f"[dim]Using default: {default}[/dim]")
            else:
                print(f"\n⚠️  Input timeout after {timeout} seconds")
                if default:
                    print(f"Using default: {default}")
            if default:
                return default
            raise TimeoutError(f"Clarification request timed out after {timeout} seconds")
        raise


def request_confirmation(message: str, default: bool = True) -> bool:
    """
    Request a yes/no confirmation from the user.
    
    Args:
        message: The message to display
        default: Default value if user just presses Enter
        
    Returns:
        True if user confirms, False otherwise
    """
    default_str = "Y/n" if default else "y/N"
    response = request_clarification(
        f"{message}\n\n[bold]Confirm?[/bold] ({default_str})",
        timeout=30,
        default="yes" if default else "no"
    )
    
    # Normalize response
    response_lower = response.lower().strip()
    if response_lower in ["yes", "y", "true", "1"]:
        return True
    elif response_lower in ["no", "n", "false", "0"]:
        return False
    else:
        # Use default if unclear
        return default


def request_choice(question: str, choices: list[str], default: Optional[str] = None) -> str:
    """
    Request the user to choose from a list of options.
    
    Args:
        question: The question to ask
        choices: List of available choices
        default: Default choice if user just presses Enter
        
    Returns:
        The selected choice
    """
    choices_str = "\n".join([f"   {i+1}. {choice}" for i, choice in enumerate(choices)])
    full_question = f"{question}\n\n{choices_str}"
    
    if default:
        full_question += f"\n\n[dim]Default: {default}[/dim]"
    
    response = request_clarification(full_question, timeout=120, default=default)
    
    # Try to match by number or exact string
    response_lower = response.lower().strip()
    
    # Check if it's a number
    try:
        choice_num = int(response_lower)
        if 1 <= choice_num <= len(choices):
            return choices[choice_num - 1]
    except ValueError:
        pass
    
    # Check if it matches a choice exactly (case-insensitive)
    for choice in choices:
        if choice.lower() == response_lower:
            return choice
    
    # If default provided and response unclear, use default
    if default:
        return default
    
    # If no match, return the response as-is (let caller handle validation)
    return response
