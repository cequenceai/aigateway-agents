#!/usr/bin/env python3
"""
Find My DM Channel - Discover your actual Slack DM channel ID

This script helps you find the correct DM channel ID for your Slack account.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_agent.auth.oauth import InMemoryTokenStorage, CallbackServer, create_oauth_provider


async def find_dm_channels(mcp_url: str):
    """Find all DM channels and identify which one is yours."""
    print("🔍 Finding your DM channels...")
    print(f"📡 Connecting to MCP server: {mcp_url}\n")
    
    # Set up OAuth
    base_url = mcp_url[:-4] if mcp_url.endswith("/mcp") else mcp_url
    storage = InMemoryTokenStorage()
    callback_server = CallbackServer(port=3033)
    callback_server.start()
    oauth_provider = create_oauth_provider(base_url, callback_server)
    
    try:
        # Check for existing tokens
        tokens = await storage.get_tokens()
        if tokens and tokens.access_token:
            print(f"✓ Found existing OAuth token")
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
        
        # Find conversationsList tool
        list_tool = None
        for tool in tools:
            if hasattr(tool, 'name') and tool.name == 'conversationsList':
                list_tool = tool
                break
        
        if not list_tool:
            print("❌ conversationsList tool not found")
            return
        
        print("📋 Listing all DM channels...")
        print("=" * 60)
        
        # Get all DMs
        try:
            result = await list_tool.ainvoke({
                "types": "im",  # Direct messages only
                "limit": 100
            })
            
            if isinstance(result, str):
                import json
                try:
                    data = json.loads(result)
                    if "channels" in data:
                        channels = data["channels"]
                        print(f"\n✅ Found {len(channels)} DM channel(s):\n")
                        
                        for i, ch in enumerate(channels, 1):
                            ch_id = ch.get("id", "Unknown")
                            user_id = ch.get("user", "Unknown")
                            is_im = ch.get("is_im", False)
                            is_open = ch.get("is_open", False)
                            
                            print(f"  {i}. Channel ID: {ch_id}")
                            print(f"     User ID: {user_id}")
                            print(f"     Is IM: {is_im}")
                            print(f"     Is Open: {is_open}")
                            
                            # Check recent messages in this channel
                            history_tool = None
                            for tool in tools:
                                if hasattr(tool, 'name') and tool.name == 'conversationsHistory':
                                    history_tool = tool
                                    break
                            
                            if history_tool:
                                try:
                                    hist_result = await history_tool.ainvoke({
                                        "channel": ch_id,
                                        "limit": 3
                                    })
                                    
                                    if isinstance(hist_result, str):
                                        hist_data = json.loads(hist_result)
                                        if "messages" in hist_data and hist_data["messages"]:
                                            latest = hist_data["messages"][0]
                                            latest_text = latest.get("text", "")[:50]
                                            print(f"     Latest message: {latest_text}...")
                                        else:
                                            print(f"     Latest message: (no messages)")
                                except:
                                    pass
                            
                            print()
                        
                        print("=" * 60)
                        print("\n💡 Your DM channel ID is likely one of the 'Channel ID' values above.")
                        print("   Look for the channel that has recent messages or is marked as 'Is Open: True'")
                        print("\n📝 To use a specific channel, set:")
                        print(f"   export MCP_TARGET_IDENTIFIER=\"<channel_id>\"")
                        
                    else:
                        print("⚠ No 'channels' field in response")
                        print(f"Response: {result[:500]}")
                except json.JSONDecodeError:
                    print(f"⚠ Response is not JSON: {result[:500]}")
            else:
                print(f"Response type: {type(result)}")
                print(f"Response: {result}")
                
        except Exception as e:
            print(f"❌ Error calling conversationsList: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Also try to get user info to help identify
        print("\n" + "=" * 60)
        print("👤 Getting your user information...")
        
        users_tool = None
        for tool in tools:
            if hasattr(tool, 'name') and tool.name == 'usersInfo':
                users_tool = tool
                break
        
        if users_tool:
            print("⚠ Note: To get your user info, we'd need your user ID.")
            print("   Check the 'User ID' in the DM channels above to find yours.")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        callback_server.stop()


async def main():
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp")
    
    print("=" * 60)
    print("Find My DM Channel Tool")
    print("=" * 60)
    print()
    
    await find_dm_channels(mcp_url)
    
    print("\n" + "=" * 60)
    print("✅ Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
