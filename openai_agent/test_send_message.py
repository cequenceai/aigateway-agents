#!/usr/bin/env python3
"""Test sending a message directly with OpenAI Agent."""

import asyncio
import os
import sys

from agents import Agent, Runner
from mcp_config import build_mcp_server
from auth.oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage


async def main():
    """Test sending a message."""
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp")
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    print(f"🔗 Connecting to MCP server: {mcp_url}")
    
    # Set up OAuth
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    storage = InMemoryTokenStorage()
    callback_server = CallbackServer(port=3033)
    callback_server.start()
    oauth_provider = create_oauth_provider(base_url, callback_server)
    
    try:
        print("📡 Building MCP server connection...")
        mcp_server = await build_mcp_server(
            mcp_url=mcp_url,
            oauth_provider=oauth_provider,
            storage=storage
        )
        
        print("🔌 Connecting to MCP server...")
        await mcp_server.connect()
        print("✅ Connected!")
        
        print("\n🤖 Creating agent...")
        agent = Agent(
            name="OpenAI Test Agent",
            instructions="""You are a helpful assistant with access to Slack MCP tools.

IMPORTANT: When sending messages, you MUST:
1. Actually call the chatPostMessage tool - do not just describe what you would do
2. Use the exact channel ID provided (e.g., D025N5FN3RT)
3. Include the prefix "OpenAI Agent: " in your message
4. Only report success if you receive a successful response from the tool

Be direct and execute the task immediately.""",
            model="gpt-4o-mini",
            mcp_servers=[mcp_server]
        )
        print("✅ Agent created!")
        
        print("\n📤 Sending message...")
        task = "Send a message to channel D025N5FN3RT saying: 'OpenAI Agent: Hello! This is a test message from OpenAI Agent. My favorite color is blue.'"
        
        result = await Runner.run(agent, task)
        
        print("\n📊 Result:")
        print(f"Final Output: {result.final_output}")
        if hasattr(result, 'steps'):
            print(f"\nSteps: {len(result.steps)}")
            for i, step in enumerate(result.steps):
                print(f"  Step {i+1}: {step}")
        
        print("\n🧹 Cleaning up...")
        await mcp_server.cleanup()
        print("✅ Done!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        callback_server.stop()


if __name__ == "__main__":
    asyncio.run(main())
