#!/usr/bin/env python3
"""Quick test to verify API key works."""

import os
import asyncio
from claude_agent_sdk import query

# Set API key
os.environ["ANTHROPIC_API_KEY"] = "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"

async def test():
    print("Testing API key...")
    try:
        async for message in query(prompt="Say hello in one word"):
            print(f"Message: {message}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
