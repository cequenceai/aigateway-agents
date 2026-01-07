# OpenAI Agent

Interactive terminal agent using the **OpenAI Agents SDK** (`openai-agents`) to interact with OpenAI models and MCP servers.

## Features

- **OpenAI Agents SDK** — Uses `openai-agents` for agent interactions
- **MCP Support** — Connect to Model Context Protocol servers
- **OAuth Authentication** — Automatic OAuth flow for protected MCP servers
- **Tool Discovery** — Automatically discover and use tools from MCP servers
- **Rich Terminal UI** — Beautiful terminal output with Rich library

## Installation

```bash
cd OPENAI_AGENT
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```python
from agents import Agent, Runner

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant."
)

result = await Runner.run(agent, "What is 2 + 2?")
print(result.final_output)
```

### With MCP Server

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

mcp_server = MCPServerStreamableHttp(
    params=MCPServerStreamableHttpParams(
        url="https://server.com/mcp",
        headers={"Authorization": "Bearer token"}
    )
)

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant with access to Slack tools.",
    mcp_servers=[mcp_server]
)

result = await Runner.run(agent, "List available Slack channels")
print(result.final_output)
```

## API Key Setup

The OpenAI Agents SDK reads the API key from the `OPENAI_API_KEY` environment variable:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Environment Variables

Required:
- `OPENAI_API_KEY` - Your OpenAI API key
- `MCP_SERVER_URL` - MCP server URL (e.g., `https://server.com/mcp`)

Optional:
- `OPENAI_MODEL` - Model to use (default: `gpt-4o-mini`)

## Testing with Slack MCP Server

### Test Connection

```bash
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://your-server.com/mcp"
python3 test_connection.py
```

### Send Message to Specific Channel

```bash
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://your-server.com/mcp"
python3 send_to_channel_id.py --channel-id "D025N5FN3RT" --message "Your message here"
```

### Send Message to User (searches for user)

```bash
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://your-server.com/mcp"
python3 send_message_to_user.py --user-name "Abhinav" --message "Your message here"
```

## Running the Agent

```bash
# Interactive chat mode
python agent.py --mcp-url https://your-server.com/mcp

# With custom model
python agent.py --mcp-url https://your-server.com/mcp --model gpt-4o-mini
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_basic_agent.py

# Run comprehensive test suite
python tests/test_comprehensive.py
```

## Project Structure

```
OPENAI_AGENT/
├── README.md
├── requirements.txt
├── agent.py              # Main CLI entry point
├── mcp_config.py         # MCP server configuration
├── test_connection.py    # Test MCP server connection
├── send_to_channel_id.py # Send message to specific channel ID
├── send_message_to_user.py # Send message by searching for user
├── agent/
│   ├── __init__.py
│   └── graph.py          # Agent setup and execution
├── auth/
│   ├── __init__.py
│   └── oauth.py          # OAuth authentication flow
└── tests/
    ├── test_basic_agent.py
    ├── test_mcp_integration.py
    └── test_comprehensive.py
```

## Key Differences from Claude Agent SDK

| Aspect | Claude Agent SDK | OpenAI Agents SDK |
|--------|------------------|-------------------|
| **Import** | `claude_agent_sdk` | `openai-agents` |
| **Main Function** | `query()` async iterator | `Runner.run()` |
| **Agent Creation** | Via `ClaudeAgentOptions` | `Agent()` class |
| **MCP Config** | Dict in options | `MCPServer*` classes |
| **OAuth** | Built-in handling | Manual required |
| **Sessions** | Built-in | `SQLiteSession` class |

## Important Notes

- **Channel IDs for DMs**: When sending DMs, you need the DM channel ID (starts with `D`), not the user ID (starts with `U`)
- **Finding Channel IDs**: Use `conversationsList` tool to find DM channel IDs
- **Context Limits**: `gpt-4o-mini` is recommended to avoid token limit issues
- **OAuth Tokens**: Stored in `~/.mcp_agent_tokens/oauth_tokens.json`

## Documentation

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [GitHub Repository](https://github.com/openai/openai-agents-python)
- [MCP Integration Guide](https://openai.github.io/openai-agents-python/mcp/)

## License

MIT
