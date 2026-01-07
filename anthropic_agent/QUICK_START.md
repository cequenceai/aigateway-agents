# Quick Start Guide - Testing with Slack MCP Server

This guide helps you quickly test the Claude Agent SDK implementation with a remote Slack MCP server.

## Prerequisites

1. **Anthropic API Key**: Set as environment variable
   ```bash
   export ANTHROPIC_API_KEY="your-api-key"
   ```

2. **MCP Server URL**: Your Slack MCP server URL
   - Example: `https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp`

3. **Dependencies**: Install all required packages
   ```bash
   pip install -r requirements.txt
   ```

## Running the Test

### Option 1: With OAuth (Recommended)

This will automatically handle OAuth authentication:

```bash
python test_slack_mcp.py --mcp-url https://your-server.com/mcp
```

**What happens:**
1. The script checks for existing OAuth tokens
2. If no tokens exist, it will:
   - Start a callback server on port 3030
   - Open your browser for OAuth authentication
   - Capture the authorization code
   - Exchange it for access tokens
   - Save tokens for future use
3. Connect to the MCP server with authentication
4. Test listing tools and using Slack MCP tools

### Option 2: With Static Auth Header

If you already have a Bearer token:

```bash
python test_slack_mcp.py --mcp-url https://your-server.com/mcp --auth-header "Bearer your-token"
```

### Option 3: Without OAuth

For testing without authentication (may fail if server requires auth):

```bash
python test_slack_mcp.py --mcp-url https://your-server.com/mcp --no-oauth
```

## What the Test Does

1. **Tool Discovery**: Lists all available tools from the MCP server
2. **Slack Tools**: Tests using Slack-specific tools:
   - `conversationsList` - Lists available Slack conversations
   - `searchMessages` - Searches for messages

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### "OAuth callback timeout"
- Check if the browser opened
- Verify you completed the OAuth flow
- Check if port 3030 is accessible
- Try manually visiting the authorization URL shown in the console

### "Connection refused" or "Server not accessible"
- Verify the MCP server URL is correct
- Check if the server is running
- Ensure your network can reach the server

### "No tools available"
- The MCP server may require authentication
- Check if OAuth completed successfully
- Verify tokens were saved (check `~/.mcp_agent_tokens/`)

## Token Storage

OAuth tokens are stored in:
```
~/.mcp_agent_tokens/oauth_tokens.json
```

To reset tokens and force a new OAuth flow, delete this file:
```bash
rm ~/.mcp_agent_tokens/oauth_tokens.json
```

## Next Steps

After successful testing, you can:
1. Use the agent interactively: `python agent.py`
2. Integrate MCP servers into your own code
3. Create custom test scripts for specific tools
