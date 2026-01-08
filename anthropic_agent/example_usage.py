#!/usr/bin/env python3
"""
Example usage of Claude Agent SDK.

This demonstrates how to use the Claude Agent SDK for various tasks.
"""

import asyncio
import os
from claude_agent_sdk import query, ClaudeAgentOptions


async def example_simple_query():
    """Example 1: Simple query without tools."""
    print("\n" + "="*80)
    print("Example 1: Simple Query")
    print("="*80)
    
    async for message in query(prompt="What is 2 + 2? Answer with just the number."):
        print(message)


async def example_with_tools():
    """Example 2: Query with tools."""
    print("\n" + "="*80)
    print("Example 2: Query with Tools")
    print("="*80)
    
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Bash"],
        permission_mode="acceptEdits",
        max_turns=5
    )
    
    async for message in query(
        prompt="Create a file called hello.txt with the text 'Hello, World!'",
        options=options
    ):
        print(message)


async def example_with_system_prompt():
    """Example 3: Query with system prompt."""
    print("\n" + "="*80)
    print("Example 3: Query with System Prompt")
    print("="*80)
    
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful coding assistant. Always provide code examples.",
        max_turns=3
    )
    
    async for message in query(
        prompt="How do I read a file in Python?",
        options=options
    ):
        print(message)


async def example_read_file():
    """Example 4: Reading a file."""
    print("\n" + "="*80)
    print("Example 4: Reading a File")
    print("="*80)
    
    # Create a test file
    test_file = "example_test.txt"
    with open(test_file, "w") as f:
        f.write("This is a test file.\nIt has multiple lines.\n")
    
    try:
        options = ClaudeAgentOptions(
            allowed_tools=["Read"],
            permission_mode="acceptEdits",
            max_turns=3
        )
        
        async for message in query(
            prompt=f"Read {test_file} and summarize its contents.",
            options=options
        ):
            print(message)
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)


async def example_edit_file():
    """Example 5: Editing a file."""
    print("\n" + "="*80)
    print("Example 5: Editing a File")
    print("="*80)
    
    # Create a test file
    test_file = "example_edit.py"
    with open(test_file, "w") as f:
        f.write("print('Hello')\n")
    
    try:
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Edit"],
            permission_mode="acceptEdits",
            max_turns=5
        )
        
        async for message in query(
            prompt=f"Edit {test_file} to print 'Hello, World!' instead of 'Hello'.",
            options=options
        ):
            print(message)
        
        # Show the result
        print("\nFile contents after edit:")
        with open(test_file, "r") as f:
            print(f.read())
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)


async def example_bash_command():
    """Example 6: Running a Bash command."""
    print("\n" + "="*80)
    print("Example 6: Running Bash Command")
    print("="*80)
    
    options = ClaudeAgentOptions(
        allowed_tools=["Bash"],
        permission_mode="acceptEdits",
        max_turns=3
    )
    
    async for message in query(
        prompt="Use Bash to list the files in the current directory.",
        options=options
    ):
        print(message)


async def main():
    """Run all examples."""
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it with: export ANTHROPIC_API_KEY='your-key'")
        return
    
    print("Claude Agent SDK Examples")
    print("="*80)
    
    # Run examples
    await example_simple_query()
    await example_with_system_prompt()
    await example_read_file()
    await example_edit_file()
    await example_bash_command()
    
    # Uncomment to run tool examples (they create/modify files)
    # await example_with_tools()


if __name__ == "__main__":
    asyncio.run(main())
