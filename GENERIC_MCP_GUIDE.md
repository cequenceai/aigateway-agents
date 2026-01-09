# Generic MCP Server Interface Guide

## Core Design Philosophy

This is a **universal, generic MCP server interface** designed to work with **any MCP server** with minimal configuration. The system is intentionally **not server-specific** - it's an "everyman" program that adapts to whatever MCP server you connect it to.

## Why Generic Design?

### 1. **Universal Compatibility**
- Works with **any MCP server** that follows the MCP protocol
- No hardcoded server-specific logic
- Adapts to server capabilities automatically

### 2. **Rapid Deployment**
- Point it at any MCP server URL and it works
- No code changes needed for different servers
- Configuration via environment variables or prompts

### 3. **Future-Proof**
- New MCP servers work immediately
- No maintenance burden for server-specific code
- Single codebase for all servers

## Architecture Decisions

### Why Environment Variables?
- **Flexibility**: Can be set per-deployment without code changes
- **Security**: API keys and URLs not in code
- **Portability**: Same code works in different environments

### Why Interactive Prompts?
- **User-Friendly**: Guides users through setup
- **Discovery**: Shows available options
- **Validation**: Catches configuration errors early

### Why Timeout Mechanisms?
- **Reliability**: Prevents hanging on unresponsive servers
- **User Experience**: Fast failure vs. indefinite wait
- **Resource Management**: Doesn't tie up resources

### Why Generic Target Identifiers?
- **Server Agnostic**: Works with channels, users, projects, etc.
- **Configurable**: Set via `MCP_TARGET_IDENTIFIER` env var
- **Optional**: Falls back to generic safety if not set

## Slack as a Demonstration Case

Slack is used as a **demonstration/test case** because:
- **Deterministic**: Known behavior and tools
- **Well-Tested**: Reliable for testing
- **Common Use Case**: Many users understand Slack

**This does NOT make the system Slack-specific.** Slack is just one example of an MCP server.

## How It Works

### 1. MCP Server Discovery
```
User provides MCP URL → System connects → Discovers available tools → Uses them
```

### 2. Tool Adaptation
- System automatically discovers tools from MCP server
- No hardcoded tool names
- Works with whatever tools the server provides

### 3. Safety Constraints
- Generic safety principles (not server-specific)
- Configurable target restrictions
- Works universally across servers

## Usage Examples

### Generic MCP Server
```bash
export MCP_SERVER_URL="https://your-mcp-server.com/mcp"
python agent_runner.py --interactive
```

### Slack (Demonstration)
```bash
export MCP_SERVER_URL="https://slack-mcp-server.com/mcp"
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"  # Optional: for Slack channel
python agent_runner.py --interactive
```

### Custom Server
```bash
python agent_runner.py \
  --mcp-url "https://custom-server.com/mcp" \
  --task "List available tools"
```

## Configuration

### Required
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` - For LLM providers

### Optional
- `MCP_SERVER_URL` - Default MCP server URL
- `MCP_TARGET_IDENTIFIER` - Target identifier (channel, user, etc.)
- `OPENAI_MODEL` - OpenAI model override
- `TAVILY_API_KEY` - For enhanced web search (Langchain only)

## Why Each Component Exists

### `agent_runner.py` - Main Orchestrator
- **Why**: Unified interface for multiple agent SDKs
- **How**: Abstracts differences between Anthropic, Langchain, OpenAI SDKs
- **Result**: Single command works with all agents

### `langchain_agent/agent/graph.py` - Langchain Integration
- **Why**: Langchain has different MCP integration than other SDKs
- **How**: Uses `langchain-mcp-adapters` for MCP connection
- **Timeout**: 30s for `get_tools()` to prevent hanging

### `anthropic_agent/mcp_config.py` - Anthropic Integration
- **Why**: Anthropic SDK has specific MCP configuration format
- **How**: Builds config dict in Anthropic SDK format
- **OAuth**: Handles OAuth flow automatically

### `openai_agent/mcp_config.py` - OpenAI Integration
- **Why**: OpenAI SDK has different MCP integration
- **How**: Uses OpenAI-specific MCP server setup
- **Compatibility**: Works with OpenAI agent SDK

## Timeout Strategy

### Why Timeouts?
- **Problem**: MCP servers can hang or be slow
- **Solution**: Timeouts at multiple levels
- **Result**: Fast failure instead of indefinite wait

### Timeout Values
- **`get_tools()`**: 30 seconds (tool discovery)
- **`run_agent_session()`**: 120 seconds (full connection + setup)
- **`agent.ainvoke()`**: 60 seconds (task execution)

### Why These Values?
- **30s for tools**: Tool discovery should be fast
- **120s for session**: Allows OAuth flow if needed
- **60s for execution**: Most tasks complete quickly

## Safety Design

### Generic Safety Principles
- **Principle of Least Privilege**: Only do what's requested
- **Principle of Caution**: When in doubt, don't do it
- **Principle of Scope Limitation**: Stay within bounds
- **Principle of Explicit Permission**: Only explicit actions
- **Principle of Minimal Impact**: Smallest set of actions

### Why Generic?
- **Universal**: Works with any server
- **Maintainable**: Single set of rules
- **Extensible**: Easy to add server-specific rules if needed

## Testing Strategy

### Slack as Test Case
- **Why**: Known, deterministic behavior
- **How**: Use Slack MCP server for testing
- **Note**: System remains generic, Slack is just test data

### Other Servers
- System should work with any MCP server
- No special handling needed
- Configuration via environment variables

## Future Extensibility

### Adding New Servers
1. Point at new MCP server URL
2. Set `MCP_TARGET_IDENTIFIER` if needed
3. Run - no code changes required

### Adding New Agents
1. Implement agent SDK integration
2. Add to `AgentRunner` class
3. Follow existing patterns

### Adding Features
- Keep generic design
- Use environment variables for configuration
- Avoid server-specific code

## Summary

This is a **universal MCP interface** that:
- Works with **any MCP server**
- Requires **minimal configuration**
- Provides **generic safety constraints**
- Uses **Slack as a demonstration case** (not a requirement)
- Designed for **rapid deployment** to any MCP server

The system is intentionally generic to maximize compatibility and minimize maintenance burden.
