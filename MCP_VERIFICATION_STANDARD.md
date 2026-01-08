# MCP Server Verification Standard

This document defines the standard approach for verifying that AI agents can effectively use MCP (Model Context Protocol) servers to complete tasks.

## Overview

The unified agent runner (`agent_runner.py`) provides a standardized way to verify that different AI agents (Anthropic, Langchain, OpenAI) can:
1. Connect to MCP servers
2. Discover available tools
3. Execute tasks using MCP tools
4. Verify task completion

## Core Principles

### 1. Generic MCP Server Support
- **No server-specific assumptions**: The runner works with any MCP server, not just Slack
- **Tool-agnostic**: Instructions don't reference specific tool names (e.g., `chatPostMessage`, `usersList`)
- **Protocol-based**: Relies on MCP protocol standards, not implementation details

### 2. Task Execution Verification
Agents must:
- Analyze task feasibility before execution
- Actually call MCP tools (not just describe what they would do)
- Verify success through tool responses
- Report incompletable tasks before attempting execution

### 3. Agent Identification
When agents produce output that needs identification:
- Prefix with agent name: `"Anthropic Agent: "`, `"Langchain Agent: "`, `"OpenAI Agent: "`
- This is optional and task-dependent

## Standard Task Format

### Task Analysis Phase
Every task includes instructions for agents to:
1. **Analyze feasibility**: Is this task completable with available MCP tools?
2. **Identify tools**: What tools would be needed?
3. **Report incompletable tasks**: State why before querying the server

### Execution Phase
Agents must:
- Actually execute using MCP tools
- Verify completion through tool responses
- Not report success without tool confirmation

## Example Tasks

### Generic Tool Discovery
```bash
python3 agent_runner.py \
  --mcp-url https://your-mcp-server.com/mcp \
  --task "List all available tools from the MCP server and describe what each one does"
```

### Multi-Step Task
```bash
python3 agent_runner.py \
  --mcp-url https://your-mcp-server.com/mcp \
  --task "First, discover what tools are available. Then, use the most appropriate tool to demonstrate its functionality."
```

### Task with Verification
```bash
python3 agent_runner.py \
  --mcp-url https://your-mcp-server.com/mcp \
  --task "Use the MCP server tools to complete a task. After completion, verify that the task was successful by checking the tool response."
```

## Verification Checklist

When testing an agent with an MCP server, verify:

- [ ] Agent can connect to MCP server
- [ ] Agent can discover available tools
- [ ] Agent can analyze task feasibility
- [ ] Agent can execute tasks using MCP tools
- [ ] Agent verifies task completion through tool responses
- [ ] Agent reports incompletable tasks appropriately
- [ ] Agent handles errors gracefully

## Agent-Specific Notes

### Anthropic Agent (Claude Agent SDK)
- Uses `claude_agent_sdk` with async iterator pattern
- OAuth handled automatically
- Good at tool discovery and multi-step tasks

### Langchain Agent
- Uses `langchain` with `MultiServerMCPClient`
- Requires explicit OAuth provider setup
- May need timeout handling for long-running tasks

### OpenAI Agent (OpenAI Agents SDK)
- Uses `openai-agents` with `Runner.run()`
- Requires manual OAuth setup
- Good at following explicit instructions

## Best Practices

1. **Start Simple**: Begin with tool discovery tasks before complex operations
2. **Test Incrementally**: Verify single tool calls before multi-step tasks
3. **Check Responses**: Always verify agents actually call tools, not just describe them
4. **Handle Errors**: Ensure agents gracefully handle incompletable tasks
5. **Generic Instructions**: Keep task instructions generic to work with any MCP server

## Common Issues

### Agent Reports Success Without Executing
- **Symptom**: Agent says task completed but no tool was called
- **Solution**: Enhanced instructions require tool response verification

### Timeout Issues
- **Symptom**: Agent hangs during execution
- **Solution**: Add timeout handling (especially for Langchain agent)

### Import Conflicts
- **Symptom**: Wrong module imported (e.g., Anthropic's `mcp_config` imported in OpenAI agent)
- **Solution**: Use temporary `sys.path` isolation for each agent

## Future Enhancements

- [ ] Automated test suite for MCP server verification
- [ ] Tool call verification and reporting
- [ ] Performance benchmarking across agents
- [ ] Support for multiple MCP servers simultaneously
- [ ] Standardized task templates for common MCP operations
