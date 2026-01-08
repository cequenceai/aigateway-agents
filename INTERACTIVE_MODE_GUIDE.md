# Interactive Mode Usage Guide

This guide explains how to use the Unified Agent Runner in interactive mode, with examples for Slack and generic MCP servers.

## Quick Start

### Basic Interactive Mode

```bash
cd three_agents
python3 agent_runner.py --mcp-url 'https://your-mcp-server.com/mcp'
```

The CLI will:
1. Prompt you to enter a task
2. Let you select which agents to use
3. Execute the task and show results
4. Display KPIs and timing information

## Slack Example

### Setup

```bash
# Set your API keys (required for agents you want to use)
export ANTHROPIC_API_KEY='your-anthropic-key-here'
export OPENAI_API_KEY='your-openai-key-here'
export OPENAI_MODEL='gpt-4o'  # Optional, defaults to gpt-4o

# Run in interactive mode
cd three_agents
python3 agent_runner.py --mcp-url 'https://your-slack-mcp-server.com/mcp'
```

### Example Session

```
╔══════════════════════════════════════════════════════════╗
║  🤖 Unified Agent Runner - Multi-Agent Task Execution     ║
╚══════════════════════════════════════════════════════════╝

Enter the task for the agents (they pick the color):
Task: Tell me about the weather in San Francisco tomorrow and DM it to me now.

Available Agents:
  1. Anthropic Agent (Claude Agent SDK)
  2. Langchain Agent (Langchain MCP)
  3. OpenAI Agent (OpenAI Agents SDK)

Select agents (comma-separated, e.g., 1,2,3 or 'all'): 3

[Agent executes task and shows results...]
```

### Important Notes for Slack

- **Channel Restriction**: All messages are automatically restricted to channel ID `D025N5FN3RT` (your DM channel)
- **No User Search**: Agents will NOT search for users or message anyone else
- **Safety First**: Agents follow a strict Code of Conduct to prevent unwanted actions

## Generic MCP Server Example

### Setup

```bash
# Set your API keys
export ANTHROPIC_API_KEY='your-anthropic-key-here'
export OPENAI_API_KEY='your-openai-key-here'
export OPENAI_MODEL='gpt-4o'

# Run with any MCP server
cd three_agents
python3 agent_runner.py --mcp-url 'https://your-mcp-server.com/mcp'
```

### Example Tasks

**Task Discovery:**
```
Task: List all available tools from the MCP server and describe what each one does
```

**Simple Action:**
```
Task: Get the current status of the system
```

**Multi-Step Task:**
```
Task: Retrieve the latest data, analyze it, and provide a summary
```

## Interactive Mode Features

### 1. Task Input
- Simply type your task as a natural language sentence
- The agents will interpret and execute it
- Examples are shown to guide you

### 2. Agent Selection
- Choose one or more agents (1, 2, 3)
- Use `all` to run all available agents
- Press Enter with no selection to use all agents

### 3. Real-Time Progress
- See progress updates as agents work
- Timestamps show when each step completes
- Status messages indicate what each agent is doing

### 4. Results Display
- Formatted tables showing execution summary
- Key Performance Indicators (KPIs)
- Timing information for each agent
- Detailed output from each agent

## Non-Interactive Mode

For automation or scripts, use flags:

```bash
python3 agent_runner.py \
  --mcp-url 'https://your-mcp-server.com/mcp' \
  --task "Your task here" \
  --agents "anthropic,openai" \
  --no-interactive
```

## Environment Variables

### Required (at least one)
- `ANTHROPIC_API_KEY` - For Anthropic Agent
- `OPENAI_API_KEY` - For OpenAI Agent and Langchain Agent (if using OpenAI)

### Optional
- `OPENAI_MODEL` - Model to use (default: `gpt-4o`)
- `MCP_SERVER_URL` - Can be set instead of using `--mcp-url` flag

## Code of Conduct

All agents follow a strict Code of Conduct:

1. **Principle of Least Privilege**: Only do what is explicitly requested
2. **Principle of Caution**: When in doubt, don't do it
3. **Principle of Scope Limitation**: Stay within bounds
4. **Principle of Explicit Permission**: Only perform explicitly requested actions
5. **Principle of Minimal Impact**: Take the smallest set of actions necessary

## Safety Constraints

For Slack specifically:
- **ONLY channel D025N5FN3RT**: All messages must go to this channel
- **No user search**: Agents will not search for or find users
- **No profile creation**: Agents will not create profiles or accounts
- **DM-only mode**: All interactions are restricted to the specified DM channel

## Troubleshooting

### Agent Not Responding
- Check that the required API key is set
- Verify the MCP server URL is correct
- Check network connectivity

### OAuth Issues
- The CLI will automatically open a browser for OAuth
- Make sure you complete the OAuth flow
- Check that OAuth callback server can be reached

### Timeout Errors
- Langchain agent has a 60-second timeout
- If tasks are timing out, try breaking them into smaller steps
- Check MCP server response times

## Examples

### Example 1: Single Agent Task
```bash
# Select only Anthropic agent
Task: Summarize the latest messages in the channel
Agents: 1
```

### Example 2: All Agents Comparison
```bash
# Run all agents on the same task
Task: Make a short post about your favorite color
Agents: all
```

### Example 3: Multi-Step Task
```bash
Task: Get the weather forecast for tomorrow, format it nicely, and send it to me
Agents: 3
```

## Tips

1. **Be Specific**: Clear tasks get better results
2. **Start Simple**: Test with simple tasks first
3. **Check Results**: Review the KPI table to see what each agent did
4. **Use Timing Logs**: Detailed timing logs are saved automatically
5. **Read Output**: Agent output shows what tools were used and what happened

## Output Files

After each run, a timing log is saved:
- `agent_timing_log_YYYYMMDD_HHMMSS.md`
- Contains detailed timing information
- Includes all agent outputs
- Useful for debugging and analysis
