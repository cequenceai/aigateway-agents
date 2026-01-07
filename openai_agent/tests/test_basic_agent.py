#!/usr/bin/env python3
"""
Basic tests for OpenAI Agent.

Tests basic functionality:
- Simple queries
- Agent creation
- Error handling
"""

import asyncio
import os
import pytest
from agents import Agent, Runner


@pytest.fixture
def api_key():
    """Ensure API key is set."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    return api_key


@pytest.mark.asyncio
async def test_simple_query(api_key):
    """Test a simple query without MCP."""
    agent = Agent(
        name="Test Agent",
        instructions="You are a helpful assistant. Answer concisely.",
    )
    
    result = await Runner.run(agent, "Say hello in exactly 3 words")
    
    assert result is not None
    assert hasattr(result, 'final_output')
    assert result.final_output is not None
    assert len(result.final_output) > 0


@pytest.mark.asyncio
async def test_agent_creation(api_key):
    """Test agent creation with custom instructions."""
    agent = Agent(
        name="Test Agent",
        instructions="You are a coding assistant. Always provide code examples.",
        model="gpt-4o",
    )
    
    assert agent.name == "Test Agent"
    assert agent.instructions is not None


@pytest.mark.asyncio
async def test_multiple_turns(api_key):
    """Test agent with multiple turns."""
    agent = Agent(
        name="Test Agent",
        instructions="You are a helpful assistant.",
    )
    
    result1 = await Runner.run(agent, "Count from 1 to 3")
    assert result1.final_output is not None
    
    result2 = await Runner.run(agent, "What comes after 3?")
    assert result2.final_output is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
