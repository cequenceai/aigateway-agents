# Anthropic Agent - Claude Agent SDK

This agent uses the **Claude Agent SDK** (`claude-agent-sdk`) to interact with Claude models. The Claude Agent SDK provides a high-level interface for building AI agents that can use tools, read files, edit code, and execute commands.

## Features

- **Claude Agent SDK** — Uses `claude-agent-sdk` for agent interactions
- **Tool Support** — Can use tools like Read, Edit, Bash, and custom MCP tools
- **Simple API** — Clean async interface using `query()` function
- **Rich Terminal UI** — Beautiful terminal output with Rich library

## Installation

```bash
cd ANTHROPIC_AGENT
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for message in query(
        prompt="Find and fix the bug in auth.py",
        options=ClaudeAgentOptions(allowed_tools=["Read", "Edit", "Bash"])
    ):
        print(message)

asyncio.run(main())
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test
python tests/test_basic_agent.py
```

## API Key Setup

The Claude Agent SDK reads the API key from the `ANTHROPIC_API_KEY` environment variable:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Or set it in your code:

```python
import os
os.environ["ANTHROPIC_API_KEY"] = "your-api-key-here"
```

## Testing with Slack MCP Server

To test with a remote Slack MCP server:

```bash
# Test with OAuth (default - will open browser for authentication)
python test_slack_mcp.py --mcp-url https://your-server.com/mcp

# Test with static auth header
python test_slack_mcp.py --mcp-url https://your-server.com/mcp --auth-header "Bearer your-token"

# Test without OAuth
python test_slack_mcp.py --mcp-url https://your-server.com/mcp --no-oauth
```

The test script will:
1. Set up OAuth authentication (if needed)
2. Connect to the MCP server
3. List available tools
4. Test using Slack MCP tools (conversationsList, searchMessages, etc.)

See `QUICK_START.md` for detailed instructions.

## Usage Examples

### Simple Query

```python
from claude_agent_sdk import query

async for message in query(prompt="What is 2 + 2?"):
    print(message)
```

### With Tools

```python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    allowed_tools=["Read", "Edit", "Bash"],
    permission_mode="acceptEdits"  # Auto-approve file edits
)

async for message in query(
    prompt="Create a hello.py file that prints 'Hello, World!'",
    options=options
):
    print(message)
```

### With System Prompt

```python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    system_prompt="You are a helpful coding assistant.",
    max_turns=5
)

async for message in query(
    prompt="Review this code for bugs",
    options=options
):
    print(message)
```

## Project Structure

```
ANTHROPIC_AGENT/
├── README.md
├── requirements.txt
├── agent.py              # Main agent implementation
└── tests/
    ├── test_basic_agent.py
    ├── test_tools.py
    └── test_mcp_integration.py
```

## Documentation

- [Claude Agent SDK Documentation](https://platform.claude.com/docs/en/agent-sdk/overview)
- [GitHub Repository](https://github.com/anthropics/claude-agent-sdk-python)

## License

MIT
