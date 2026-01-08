# aigateway-agents
Cequence AI Gateway Agent Examples

This repository contains three complete agent implementations with generic MCP (Model Context Protocol) server connectors:

1. **Anthropic Agent** - Uses Claude Agent SDK
2. **Langchain Agent** - Uses Langchain with MCP integration
3. **OpenAI Agent** - Uses OpenAI Agents SDK

## Features

- ✅ **Generic MCP Connectors** - Works with any MCP server (not just Slack)
- ✅ **OAuth Support** - Automatic OAuth flow for protected MCP servers
- ✅ **Multiple Authentication Methods** - Static headers, OAuth, or token storage
- ✅ **Comprehensive Tests** - Test suites for each agent
- ✅ **Unified Agent Runner** - Run tasks across multiple agents with a single CLI
- ✅ **Example Implementations** - Slack MCP server used as example

## Quick Start

### Unified Agent Runner (Recommended)

Run tasks across all three agents with a single command:

```bash
cd three_agents
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
python3 agent_runner.py --mcp-url https://your-mcp-server.com/mcp
```

### Individual Agents

#### Anthropic Agent (Claude Agent SDK)

```bash
cd anthropic_agent
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"
python agent.py --mcp-url https://your-mcp-server.com/mcp
```

#### Langchain Agent

```bash
cd langchain_agent
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"  # or OPENAI_API_KEY
python mcp_agent.py --mcp-url https://your-mcp-server.com/mcp
```

#### OpenAI Agent

```bash
cd openai_agent
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
python agent.py --mcp-url https://your-mcp-server.com/mcp
```

## Testing

Each agent includes test suites:

```bash
# Anthropic Agent
cd anthropic_agent
pytest tests/

# OpenAI Agent
cd openai_agent
pytest tests/

# Langchain Agent
cd langchain_agent
python -m pytest tests/
```

## MCP Server Examples

While these agents work with **any** MCP server, common examples include:

- **Slack MCP Server** - For Slack integration (used in examples)
- **GitHub MCP Server** - For GitHub operations
- **File System MCP** - For file operations
- **Custom MCP Servers** - Any MCP-compliant server

## Structure

```
three_agents/
├── anthropic_agent/     # Claude Agent SDK implementation
├── langchain_agent/      # Langchain MCP agent
├── openai_agent/         # OpenAI Agents SDK implementation
├── agent_runner.py       # Unified agent runner CLI
└── README.md            # This file
```

Each agent directory contains:
- Core agent implementation
- MCP connector (generic, works with any MCP server)
- OAuth authentication module
- Test suites
- Documentation

## License

MIT
