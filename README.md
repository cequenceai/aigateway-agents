# Universal MCP Agent Runner

A unified CLI tool for running tasks across multiple AI agents with **any MCP (Model Context Protocol) server**.

## Features

- 🤖 **Three Agent Implementations**
  - **Anthropic Agent** - Claude Agent SDK
  - **Langchain Agent** - Langchain with MCP integration  
  - **OpenAI Agent** - OpenAI Agents SDK

- 🔌 **Universal MCP Support** - Works with any MCP-compliant server
- 🔐 **OAuth Authentication** - Automatic OAuth flow for protected servers
- 📊 **Real-time Progress** - Clean timestamped status updates
- 🎯 **Target Channel Support** - Direct channel/user targeting (e.g., Slack DM)
- 🐛 **Debug Mode** - Verbose logging when needed

## Quick Start

### 1. Install Dependencies

```bash
cd three_agents
pip install -r requirements.txt
```

### 2. Set API Keys

Create a `.env` file or export environment variables:

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export OPENAI_API_KEY="your-openai-key"
```

### 3. Run

```bash
# Interactive mode (prompts for task)
python3 agent_runner.py --mcp-url "https://your-mcp-server.com/mcp"

# With task specified
python3 agent_runner.py \
  --mcp-url "https://your-mcp-server.com/mcp" \
  --agents all \
  --task "Send a hello message"

# With target channel (e.g., Slack DM)
python3 agent_runner.py \
  --mcp-url "https://your-mcp-server.com/mcp" \
  --target-channel "D025N5FN3RT" \
  --agents all \
  --task "Send me a fun fact"
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--mcp-url` | MCP server URL (required) |
| `--agents` | Agents to run: `anthropic`, `langchain`, `openai`, or `all` |
| `--task` | Task to execute (prompts if not provided) |
| `--target-channel` | Target channel/user ID for messaging |
| `--debug` | Enable verbose logging |
| `--no-interactive` | Disable interactive mode |
| `--temperature` | Model temperature (0.0-2.0) |
| `--openai-model` | OpenAI model to use (e.g., `gpt-4o`) |

## Example Output

```
📁 Loaded .env file from /path/to/.env

╔══════════════════════════════════════════════════════════╗
║  🤖 Unified Agent Runner - Multi-Agent Task Execution     ║
╚══════════════════════════════════════════════════════════╝

🔍 Checking API keys...
✓ ANTHROPIC_API_KEY: ✓ Valid and active
✓ OPENAI_API_KEY: ✓ Valid and active

Running agents in parallel with round-robin input queue...

[00:07:46] Langchain Agent: Starting...
[00:07:46] Langchain Agent: Connecting to MCP server...
[00:07:48] Langchain Agent: Interpreting and executing task...
[00:07:57] Langchain Agent: ✅ Complete

╔══════════════════════════════════════════════════════════╗
║  📊 Execution Results                                   ║
╚══════════════════════════════════════════════════════════╝

┌─────────────────┬────────────┬────────┬─────────────┐
│ Agent           │ Status     │ Time   │ Tool Calls  │
├─────────────────┼────────────┼────────┼─────────────┤
│ Langchain Agent │ ✅ Success │ 11.03s │ 20          │
└─────────────────┴────────────┴────────┴─────────────┘
```

## Project Structure

```
three_agents/
├── agent_runner.py          # Unified CLI (main entry point)
├── anthropic_agent/         # Claude Agent SDK implementation
│   ├── agent.py
│   ├── mcp_config.py
│   └── auth.py
├── langchain_agent/         # Langchain MCP agent
│   ├── mcp_agent.py
│   ├── mcp_config.py
│   └── oauth.py
├── openai_agent/            # OpenAI Agents SDK implementation
│   ├── agent.py
│   ├── mcp_config.py
│   └── oauth.py
├── requirements.txt
└── .env.example
```

## MCP Server Compatibility

Works with **any** MCP-compliant server:

- **Slack MCP** - Messaging and workspace tools
- **GitHub MCP** - Repository and issue management
- **File System MCP** - Local file operations
- **Custom MCP Servers** - Any server implementing the MCP protocol

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `OPENAI_API_KEY` | OpenAI API key |
| `MCP_SERVER_URL` | Default MCP server URL |
| `MCP_TARGET_IDENTIFIER` | Default target channel/user |
| `OPENAI_MODEL` | Default OpenAI model |

## Clarification Handling

When agents need clarification, they'll prompt you:

```
╭─────────────────────────── Clarification Request ────────────────────────────╮
│ 🤖 Langchain Agent needs clarification:                                      │
│                                                                              │
│ What message should I send?                                                  │
╰──────────────────────────────────────────────────────────────────────────────╯

Your response: Hello world!
```

Use `--target-channel` to skip channel-related questions.

## Debug Mode

Enable verbose logging with `--debug`:

```bash
python3 agent_runner.py --mcp-url "..." --debug
```

Shows detailed information about:
- MCP connection attempts
- Clarification detection
- Tool calls and responses

## License

MIT
