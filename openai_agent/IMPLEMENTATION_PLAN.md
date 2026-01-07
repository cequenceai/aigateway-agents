# OpenAI Agent Implementation Plan

## Research Summary

Based on research of the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) and [GitHub repository](https://github.com/openai/openai-agents-python), here's the implementation plan.

## Key Findings

### 1. OpenAI Agents SDK Overview
- **Package**: `openai-agents` (not `openai`)
- **Core Concepts**: Agents, Handoffs, Guardrails, Sessions, Tracing
- **MCP Support**: Built-in support via `MCPServerStreamableHttp`, `MCPServerSse`, `MCPServerStdio`
- **OAuth**: Supported via headers in MCP server params

### 2. MCP Integration Pattern

The SDK uses different MCP server classes:
- `MCPServerStreamableHttp` - For HTTP MCP servers (most common)
- `MCPServerSse` - For Server-Sent Events
- `MCPServerStdio` - For local subprocesses

**Key Pattern:**
```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

mcp_server = MCPServerStreamableHttp(
    name="Slack MCP",
    params={
        "url": "https://server.com/mcp",
        "headers": {
            "Authorization": "Bearer token"
        }
    }
)

agent = Agent(
    name="Assistant",
    instructions="...",
    mcp_servers=[mcp_server]
)

result = await Runner.run(agent, "query")
```

### 3. OAuth Handling

Unlike Claude Agent SDK which handles OAuth internally, OpenAI Agents SDK requires:
- **Manual OAuth flow** - We need to handle OAuth ourselves
- **Token in headers** - Pass Bearer token in `params.headers`
- **Token refresh** - Handle token expiration manually

## Implementation Plan

### Phase 1: Core Structure (Following MCP_AGENT pattern)

#### File Structure
```
OPENAI_AGENT/
├── README.md                    # Documentation
├── requirements.txt             # Dependencies
├── agent.py                     # Main CLI entry point
├── agent/
│   ├── __init__.py
│   └── graph.py                 # Agent setup and execution
├── auth/
│   ├── __init__.py
│   └── oauth.py                 # OAuth flow (reuse from MCP_AGENT)
├── mcp_config.py                # MCP server configuration
└── tests/
    ├── test_basic_agent.py
    ├── test_mcp_integration.py
    └── test_comprehensive.py
```

#### Key Differences from Claude Agent SDK
1. **SDK Import**: `from agents import Agent, Runner` (not `claude_agent_sdk`)
2. **MCP Server**: `MCPServerStreamableHttp` (not dict config)
3. **OAuth**: Manual handling required (not built-in)
4. **Agent Creation**: `Agent()` class (not `query()` function)
5. **Execution**: `Runner.run()` (not async iterator)

### Phase 2: Implementation Steps

#### Step 1: Setup Dependencies
```python
# requirements.txt
openai-agents>=0.6.0
openai>=1.0.0
rich>=13.0.0
mcp>=1.0.0
httpx>=0.27.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
```

#### Step 2: OAuth Module (Reuse from MCP_AGENT)
- Copy `auth/oauth.py` from MCP_AGENT
- Adapt for OpenAI Agents SDK needs
- Token storage and callback server remain the same

#### Step 3: MCP Configuration Module
```python
# mcp_config.py
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

async def build_mcp_server(
    mcp_url: str,
    auth_header: str | None = None,
    oauth_provider = None,
    storage = None
) -> MCPServerStreamableHttp:
    """Build MCP server instance for OpenAI Agents SDK."""
    # Handle OAuth if needed
    # Extract token
    # Create MCPServerStreamableHttp with headers
```

#### Step 4: Agent Setup
```python
# agent/graph.py
from agents import Agent
from agents.mcp import MCPServerStreamableHttp

class AgentConfig:
    mcp_url: str
    provider: str = "openai"
    model: str = "gpt-4o"
    auth_header: str | None = None
    oauth_provider = None

async def create_agent(config: AgentConfig) -> Agent:
    """Create OpenAI Agent with MCP server."""
    mcp_server = await build_mcp_server(...)
    
    agent = Agent(
        name="OpenAI Agent",
        instructions="You are a helpful assistant with access to Slack tools.",
        mcp_servers=[mcp_server]
    )
    
    return agent
```

#### Step 5: CLI Interface
```python
# agent.py
from agents import Runner
from agent.graph import create_agent, AgentConfig

async def main():
    config = AgentConfig(mcp_url=args.mcp_url)
    agent = await create_agent(config)
    
    # Interactive loop
    while True:
        user_input = input("You: ")
        result = await Runner.run(agent, user_input)
        print(f"Assistant: {result.final_output}")
```

### Phase 3: OAuth Integration Strategy

**Challenge**: OpenAI Agents SDK doesn't handle OAuth automatically.

**Solution**: 
1. Use existing OAuth module from MCP_AGENT
2. Trigger OAuth before creating MCP server
3. Extract token and pass in headers
4. Handle token refresh manually

**Implementation**:
```python
# In mcp_config.py
async def build_mcp_server(...):
    # 1. Check for existing tokens
    tokens = await storage.get_tokens()
    
    # 2. If no tokens, trigger OAuth
    if not tokens and oauth_provider:
        # Use langchain-mcp-adapters to trigger OAuth
        from langchain_mcp_adapters.client import MultiServerMCPClient
        client = MultiServerMCPClient({...})
        await client.get_tools()  # Triggers OAuth
        tokens = await storage.get_tokens()
    
    # 3. Extract token
    auth_token = tokens.access_token if tokens else None
    
    # 4. Create MCP server with token
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    return MCPServerStreamableHttp(
        name="slack_mcp",
        params=MCPServerStreamableHttpParams(
            url=mcp_url,
            headers=headers
        )
    )
```

### Phase 4: Testing Strategy

#### Test Structure (Following MCP_AGENT pattern)
1. **Basic Agent Test**: Simple query without MCP
2. **MCP Connection Test**: OAuth and server connection
3. **Tool Discovery Test**: List available tools
4. **Tool Usage Test**: Use Slack tools (send message, search)
5. **Error Handling Test**: Invalid inputs, network errors

#### Test File Structure
```python
# tests/test_comprehensive.py
class OpenAIAgentTester:
    async def test_basic_query()
    async def test_mcp_connection()
    async def test_tool_discovery()
    async def test_send_message()
    async def test_error_handling()
```

### Phase 5: Key Implementation Details

#### 1. Agent Lifecycle Management
- **Connection**: `await mcp_server.connect()` before use
- **Cleanup**: `await mcp_server.cleanup()` after use
- **Context Manager**: Use `async with` for automatic cleanup

#### 2. Session Management
```python
from agents import SQLiteSession

session = SQLiteSession("user_123")
result = await Runner.run(agent, "query", session=session)
```

#### 3. Error Handling
- Network errors: Retry logic
- OAuth errors: Re-trigger flow
- Tool errors: Graceful degradation

#### 4. Tool Filtering
- Can specify which tools to expose
- Use `allowed_tools` parameter in Agent

## Comparison: OpenAI vs Claude Agent SDK

| Feature | Claude Agent SDK | OpenAI Agents SDK |
|---------|------------------|------------------|
| **Import** | `claude_agent_sdk` | `openai-agents` |
| **Main Function** | `query()` async iterator | `Runner.run()` |
| **Agent Creation** | Via `ClaudeAgentOptions` | `Agent()` class |
| **MCP Config** | Dict in options | `MCPServer*` classes |
| **OAuth** | Built-in handling | Manual required |
| **Sessions** | Built-in | `SQLiteSession` class |
| **Tools** | Auto-discovered | Auto-discovered |
| **Handoffs** | Not available | Available |
| **Guardrails** | Not available | Available |

## Implementation Checklist

### Core Implementation
- [ ] Create file structure
- [ ] Setup requirements.txt
- [ ] Implement OAuth module (adapt from MCP_AGENT)
- [ ] Implement MCP configuration module
- [ ] Implement agent setup (agent/graph.py)
- [ ] Implement CLI interface (agent.py)

### OAuth Integration
- [ ] Adapt OAuth module for OpenAI SDK
- [ ] Implement token extraction
- [ ] Implement token refresh logic
- [ ] Test OAuth flow end-to-end

### Testing
- [ ] Basic agent test
- [ ] MCP connection test
- [ ] Tool discovery test
- [ ] Tool usage test (send message)
- [ ] Error handling test
- [ ] Comprehensive test suite

### Documentation
- [ ] README.md with examples
- [ ] Quick start guide
- [ ] API documentation
- [ ] Troubleshooting guide

## Next Steps

1. **Create file structure** following MCP_AGENT pattern
2. **Implement OAuth module** (reuse and adapt)
3. **Implement MCP configuration** for OpenAI SDK
4. **Create agent setup** using OpenAI Agents SDK
5. **Build CLI interface** with Rich UI
6. **Create test suite** following MCP_AGENT pattern
7. **Test with Slack MCP server**
8. **Document and commit**

## References

- [OpenAI Agents SDK Docs](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK GitHub](https://github.com/openai/openai-agents-python)
- [MCP Integration Guide](https://openai.github.io/openai-agents-python/mcp/)
- [MCP_AGENT Reference](../MCP_AGENT_REFERENCE/STRUCTURE_GUIDE.md)
