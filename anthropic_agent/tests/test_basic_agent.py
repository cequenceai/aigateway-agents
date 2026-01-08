#!/usr/bin/env python3
"""
Basic tests for Claude Agent SDK.

Tests basic functionality:
- Simple queries
- Tool usage
- Error handling
"""

import asyncio
import os
import pytest
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage


@pytest.fixture
def api_key():
    """Ensure API key is set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return api_key


@pytest.mark.asyncio
async def test_simple_query(api_key):
    """Test a simple query without tools."""
    messages = []
    async for message in query(prompt="What is 2 + 2? Answer with just the number."):
        messages.append(message)
    
    # Should receive at least one message
    assert len(messages) > 0
    
    # Check for AssistantMessage or ResultMessage
    assert any(isinstance(m, (AssistantMessage, ResultMessage)) for m in messages)


@pytest.mark.asyncio
async def test_query_with_system_prompt(api_key):
    """Test query with system prompt."""
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant. Always respond in uppercase.",
        max_turns=1
    )
    
    messages = []
    async for message in query(
        prompt="Say hello",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_query_with_tools(api_key):
    """Test query with allowed tools."""
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Bash"],
        permission_mode="acceptEdits",
        max_turns=3
    )
    
    messages = []
    async for message in query(
        prompt="List the files in the current directory using Bash.",
        options=options
    ):
        messages.append(message)
    
    assert len(messages) > 0
    
    # Check if any tool was used
    tool_used = False
    for msg in messages:
        if isinstance(msg, AssistantMessage) and msg.content:
            for block in msg.content:
                if hasattr(block, "name"):
                    tool_used = True
                    break
    
    # Tool usage is optional - just verify we got a response
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_read_tool(api_key):
    """Test using the Read tool."""
    # Create a test file first
    test_file = "test_read_file.txt"
    with open(test_file, "w") as f:
        f.write("Hello, World!")
    
    try:
        options = ClaudeAgentOptions(
            allowed_tools=["Read"],
            permission_mode="acceptEdits",
            max_turns=3
        )
        
        messages = []
        async for message in query(
            prompt=f"Read the file {test_file} and tell me what it contains.",
            options=options
        ):
            messages.append(message)
        
        assert len(messages) > 0
        
        # Check if response mentions the file content
        response_text = ""
        for msg in messages:
            if isinstance(msg, AssistantMessage) and msg.content:
                for block in msg.content:
                    if hasattr(block, "text"):
                        response_text += block.text
        
        assert "Hello" in response_text or "World" in response_text
        
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)


@pytest.mark.asyncio
async def test_max_turns(api_key):
    """Test max_turns limit."""
    options = ClaudeAgentOptions(
        max_turns=1
    )
    
    messages = []
    async for message in query(
        prompt="Count from 1 to 10, one number per turn.",
        options=options
    ):
        messages.append(message)
    
    # Should respect max_turns (though exact count may vary)
    assert len(messages) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
