#!/usr/bin/env python3
"""
Verify Slack Message - Check if a message was actually sent to Slack

This script helps verify if messages are actually being sent to Slack
by checking the conversation history.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_agent.auth.oauth import InMemoryTokenStorage, CallbackServer, create_oauth_provider


async def verify_message(mcp_url: str, channel_id: str = "D025N5FN3RT"):
    """Verify if messages exist in the channel."""
    print(f"🔍 Verifying messages in channel: {channel_id}")
    print(f"📡 Connecting to MCP server: {mcp_url}\n")
    
    # Set up OAuth
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    storage = InMemoryTokenStorage()
    callback_server = CallbackServer(port=3032)
    callback_server.start()
    oauth_provider = create_oauth_provider(base_url, callback_server)
    
    try:
        # Check for existing tokens
        tokens = await storage.get_tokens()
        if tokens and tokens.access_token:
            print(f"✓ Found existing OAuth token (length: {len(tokens.access_token)})")
            auth_token = tokens.access_token
        else:
            print("⚠ No token found - will trigger OAuth")
            auth_token = None
        
        # Build config
        mcp_config = {
            "mcp_server": {
                "transport": "http",
                "url": mcp_url,
            }
        }
        
        if auth_token:
            mcp_config["mcp_server"]["headers"] = {
                "Authorization": f"Bearer {auth_token}"
            }
        else:
            mcp_config["mcp_server"]["auth"] = oauth_provider
        
        # Create client
        client = MultiServerMCPClient(mcp_config)
        
        # Get tools
        print("📋 Fetching tools...")
        tools = await client.get_tools()
        print(f"✓ Got {len(tools)} tools\n")
        
        # Find conversationsHistory tool
        history_tool = None
        for tool in tools:
            if hasattr(tool, 'name') and tool.name == 'conversationsHistory':
                history_tool = tool
                break
        
        if not history_tool:
            print("❌ conversationsHistory tool not found")
            return
        
        print(f"📨 Checking conversation history for channel: {channel_id}")
        print("=" * 60)
        
        # Call conversationsHistory
        try:
            # Use the tool directly
            result = await history_tool.ainvoke({
                "channel": channel_id,
                "limit": 10
            })
            
            print(f"\n✅ Got response from conversationsHistory")
            print(f"Response type: {type(result)}")
            print(f"Response: {result}\n")
            
            # Try to parse the response
            if isinstance(result, str):
                import json
                try:
                    data = json.loads(result)
                    if "messages" in data:
                        messages = data["messages"]
                        print(f"📬 Found {len(messages)} recent messages in channel {channel_id}:\n")
                        for i, msg in enumerate(messages[:5], 1):
                            text = msg.get("text", "No text")
                            user = msg.get("user", "Unknown")
                            ts = msg.get("ts", "Unknown")
                            print(f"  {i}. [{ts}] User: {user}")
                            print(f"     Text: {text[:100]}...")
                            print()
                    else:
                        print("⚠ No 'messages' field in response")
                        print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                except json.JSONDecodeError:
                    print(f"⚠ Response is not JSON: {result[:200]}")
            else:
                print(f"Response: {result}")
                
        except Exception as e:
            print(f"❌ Error calling conversationsHistory: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Also try to get channel info
        print("\n" + "=" * 60)
        print("🔍 Checking channel information...")
        
        list_tool = None
        for tool in tools:
            if hasattr(tool, 'name') and tool.name == 'conversationsList':
                list_tool = tool
                break
        
        if list_tool:
            try:
                result = await list_tool.ainvoke({
                    "types": "im",  # Direct messages
                    "limit": 50
                })
                
                if isinstance(result, str):
                    import json
                    try:
                        data = json.loads(result)
                        if "channels" in data:
                            channels = data["channels"]
                            print(f"\n📋 Found {len(channels)} DM channels:")
                            for ch in channels:
                                ch_id = ch.get("id", "Unknown")
                                user = ch.get("user", "Unknown")
                                is_im = ch.get("is_im", False)
                                if is_im:
                                    print(f"  • Channel: {ch_id}, User: {user}")
                                    if ch_id == channel_id:
                                        print(f"    ✅ This matches your target channel!")
                        else:
                            print("⚠ No 'channels' field in response")
                    except json.JSONDecodeError:
                        print(f"⚠ Response is not JSON")
            except Exception as e:
                print(f"⚠ Error calling conversationsList: {e}")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        callback_server.stop()


async def main():
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp")
    channel_id = os.environ.get("MCP_TARGET_IDENTIFIER", "D025N5FN3RT")
    
    print("=" * 60)
    print("Slack Message Verification Tool")
    print("=" * 60)
    print()
    
    await verify_message(mcp_url, channel_id)
    
    print("\n" + "=" * 60)
    print("💡 Tips:")
    print("  • If no messages appear, the channel ID might be wrong")
    print("  • Check that D025N5FN3RT is your actual DM channel")
    print("  • Try listing channels to find the correct DM channel ID")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
