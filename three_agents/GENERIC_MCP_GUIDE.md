# Generic MCP Server Guide

This system is a **universal MCP interface** designed to work with **any MCP server** with minimal configuration.

## Core Design Philosophy

- **Universal Compatibility**: Works with any MCP server that follows the MCP protocol
- **Rapid Deployment**: Point it at any MCP server URL and it works
- **No Hardcoding**: All values are configurable via environment variables
- **Future-Proof**: New MCP servers work immediately without code changes

## Quick Start

```bash
# Set your API keys
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"

# Set your MCP server URL
export MCP_SERVER_URL="https://your-mcp-server.com/mcp"

# Optional: Set target identifier (channel ID, user ID, etc.)
export MCP_TARGET_IDENTIFIER="your-target-id"

# Run
python3 agent_runner.py --mcp-url "$MCP_SERVER_URL"
```

## Configuration

### Required
- `ANTHROPIC_API_KEY` - For Anthropic Agent
- `OPENAI_API_KEY` - For OpenAI/Langchain Agents

### Optional
- `MCP_SERVER_URL` - Default MCP server URL
- `MCP_TARGET_IDENTIFIER` - Target identifier (channel, user, etc.)
- `OPENAI_MODEL` - OpenAI model override (default: `gpt-4o`)
- `TAVILY_API_KEY` - For enhanced web search (Langchain only)

## Examples

### Generic MCP Server
```bash
python3 agent_runner.py \
  --mcp-url "https://your-mcp-server.com/mcp" \
  --task "List available tools"
```

### With Target Identifier
```bash
export MCP_TARGET_IDENTIFIER="channel-123"
python3 agent_runner.py \
  --mcp-url "https://your-mcp-server.com/mcp" \
  --task "Send a message"
```

## Safety Constraints

The system maintains **generic safety principles** that work with any MCP server:

1. **Principle of Least Privilege** - Only do what's explicitly requested
2. **Principle of Caution** - When in doubt, don't do it
3. **Principle of Scope Limitation** - Stay within bounds
4. **Principle of Explicit Permission** - Only perform explicitly requested actions
5. **Principle of Minimal Impact** - Take smallest set of actions necessary

## Architecture

### Why Environment Variables?
- **Flexibility**: Can be set per-deployment without code changes
- **Security**: API keys and URLs not in code
- **Portability**: Same code works in different environments

### Why Generic Design?
- **Universal**: Works with any MCP server
- **Maintainable**: Single codebase for all servers
- **Extensible**: Easy to add server-specific rules if needed

## MCP Server Requirements

Works with **any MCP server** that:
- Provides tools via MCP protocol
- Supports HTTP transport
- Optionally supports OAuth 2.0 authentication

No server-specific code or configurations required.

## Deployment Checklist

- [ ] Set API keys (`ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`)
- [ ] Set MCP server URL (`--mcp-url` or `MCP_SERVER_URL`)
- [ ] Optionally set target identifier (`MCP_TARGET_IDENTIFIER`)
- [ ] Run the agent runner
- [ ] Agents automatically discover and use MCP server tools

That's it! No other configuration needed.
