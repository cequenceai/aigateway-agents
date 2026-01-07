#!/usr/bin/env python3
"""
Tests for tool usage with Claude Agent SDK.

Tests various tools:
- Read tool
- Edit tool
- Bash tool
"""

import asyncio
import os
import pytest
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


@pytest.fixture
def api_key():
    """Ensure API key is set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return api_key


@pytest.fixture
def test_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.mark.asyncio
async def test_read_file(api_key, test_dir):
    """Test reading a file."""
    test_file = test_dir / "test.txt"
    test_file.write_text("This is a test file.")
    
    options = ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits",
        max_turns=3
    )
    
    messages = []
    async for message in query(
        prompt=f"Read the file {test_file} and tell me its contents.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_edit_file(api_key, test_dir):
    """Test editing a file."""
    test_file = test_dir / "test.py"
    test_file.write_text("print('Hello')\n")
    
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Edit"],
        permission_mode="acceptEdits",
        max_turns=5
    )
    
    messages = []
    async for message in query(
        prompt=f"Edit {test_file} to print 'Hello, World!' instead of 'Hello'.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0
    
    # Check if file was modified
    content = test_file.read_text()
    assert "World" in content


@pytest.mark.asyncio
async def test_bash_command(api_key):
    """Test running a Bash command."""
    options = ClaudeAgentOptions(
        allowed_tools=["Bash"],
        permission_mode="acceptEdits",
        max_turns=3
    )
    
    messages = []
    async for message in query(
        prompt="Use Bash to run 'echo Hello, World!' and tell me the output.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_multiple_tools(api_key, test_dir):
    """Test using multiple tools in one query."""
    test_file = test_dir / "data.txt"
    test_file.write_text("Line 1\nLine 2\nLine 3\n")
    
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Bash"],
        permission_mode="acceptEdits",
        max_turns=10
    )
    
    messages = []
    async for message in query(
        prompt=f"Read {test_file}, count the lines using Bash, and add a comment at the top of the file with the line count.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_create_file(api_key, test_dir):
    """Test creating a new file."""
    test_file = test_dir / "new_file.py"
    
    options = ClaudeAgentOptions(
        allowed_tools=["Edit"],
        permission_mode="acceptEdits",
        max_turns=5
    )
    
    messages = []
    async for message in query(
        prompt=f"Create a new file {test_file} with a Python function that returns 'Hello, World!'.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0
    
    # Check if file was created
    assert test_file.exists()
    content = test_file.read_text()
    assert "Hello" in content or "World" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
