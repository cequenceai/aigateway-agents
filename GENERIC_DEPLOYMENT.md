# Generic Deployment Guide

This system is designed for **rapid, out-of-the-box deployment** with any MCP server. No hardcoded values, no server-specific configurations required.

## Quick Start (Generic)

```bash
# Set your API keys
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"

# Set your MCP server URL
export MCP_SERVER_URL="https://your-mcp-server.com/mcp"

# Optional: Set target identifier if your MCP server requires it
# (e.g., channel ID, user ID, etc.)
export MCP_TARGET_IDENTIFIER="your-target-id"

# Run
python3 agent_runner.py --mcp-url "$MCP_SERVER_URL"
```

## Configuration via Environment Variables

### Required
- `ANTHROPIC_API_KEY` - For Anthropic Agent (or `OPENAI_API_KEY` for Langchain/OpenAI)
- `OPENAI_API_KEY` - For OpenAI/Langchain Agents

### Optional
- `MCP_TARGET_IDENTIFIER` - Target identifier for messaging (e.g., channel ID, user ID)
  - If not set, agents use generic target restrictions
  - If set, agents are instructed to use this specific target
- `OPENAI_MODEL` - OpenAI model to use (default: `gpt-4o`)
- `TAVILY_API_KEY` - For enhanced web search (Langchain agent only)

## Generic vs. Server-Specific

### Generic Mode (Default)
When `MCP_TARGET_IDENTIFIER` is **not set**:
- Agents use generic safety constraints
- No hardcoded target restrictions
- Works with any MCP server
- Agents follow task instructions for target selection

### Server-Specific Mode
When `MCP_TARGET_IDENTIFIER` **is set**:
- Agents are instructed to use the specified target identifier
- Safety constraints include target-specific restrictions
- Useful for production deployments with known targets

## Examples

### Example 1: Generic MCP Server (No Target)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."

python3 agent_runner.py \
  --mcp-url "https://generic-mcp-server.com/mcp" \
  --task "List available tools"
```

### Example 2: Slack MCP Server (With Target)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"  # Channel ID

python3 agent_runner.py \
  --mcp-url "https://slack-mcp-server.com/mcp" \
  --task "Send a message saying hello"
```

### Example 3: Custom MCP Server
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export MCP_TARGET_IDENTIFIER="user-12345"  # User ID

python3 agent_runner.py \
  --mcp-url "https://custom-mcp-server.com/mcp" \
  --task "Send notification to user"
```

## Safety Constraints

The system maintains **generic safety constraints** that work with any MCP server:

1. **Principle of Least Privilege** - Only do what's explicitly requested
2. **Principle of Caution** - When in doubt, don't do it
3. **Principle of Scope Limitation** - Stay within bounds
4. **Principle of Explicit Permission** - Only perform explicitly requested actions
5. **Principle of Minimal Impact** - Take smallest set of actions necessary

These constraints are **not server-specific** and work universally.

## MCP Server Requirements

The system works with **any MCP server** that:
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

## Benefits of Generic Design

1. **Rapid Deployment** - Works immediately with any MCP server
2. **No Hardcoding** - All values are configurable
3. **Universal Safety** - Safety constraints work with any server
4. **Flexible** - Can be deployed to different environments without code changes
5. **Maintainable** - Single codebase for all MCP servers
