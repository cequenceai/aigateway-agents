# Unified Agent Runner

A beautiful CLI interface to run tasks across multiple AI agents (Anthropic, Langchain, OpenAI) using a single MCP server.

## Features

- ✅ **Multi-Agent Support** - Run the same task across multiple agents
- ✅ **Agent Selection** - Choose which agents to use interactively
- ✅ **Parallel Execution** - Agents run in parallel for faster results
- ✅ **Beautiful Output** - Rich terminal UI with formatted results
- ✅ **Error Handling** - Graceful error handling and reporting
- ✅ **Task Validation** - Agents can report if tasks are incompletable

## Quick Start

```bash
cd three_agents
python agent_runner.py --mcp-url https://your-mcp-server.com/mcp
```

## Usage

### Interactive Mode

```bash
python agent_runner.py --mcp-url https://your-mcp-server.com/mcp
```

The CLI will:
1. Prompt you to enter a task
2. Let you select which agents to use
3. Run the task across all selected agents
4. Display results in a formatted table

### Non-Interactive Mode

```bash
python agent_runner.py \
  --mcp-url https://your-mcp-server.com/mcp \
  --task "Send a message to user Abhinav saying Hello" \
  --agents "anthropic,openai"
```

### Select All Agents

```bash
python agent_runner.py \
  --mcp-url https://your-mcp-server.com/mcp \
  --task "Your task here" \
  --agents "all"
```

## Environment Variables

Required (at least one):
- `ANTHROPIC_API_KEY` - For Anthropic Agent
- `OPENAI_API_KEY` - For OpenAI Agent and Langchain Agent (if using OpenAI)

Optional:
- `OPENAI_MODEL` - OpenAI model to use (default: `gpt-4o-mini`)

## Examples

### Example 1: Send a Slack Message

```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://slack-mcp-server.com/mcp"

python agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --task "Send a message to user Abhinav saying 'Hello from all agents!'" \
  --agents "all"
```

### Example 2: List Available Tools

```bash
python agent_runner.py \
  --mcp-url https://your-mcp-server.com/mcp \
  --task "List all available tools from the MCP server" \
  --agents "anthropic,langchain"
```

### Example 3: With Static Auth Header

```bash
python agent_runner.py \
  --mcp-url https://your-mcp-server.com/mcp \
  --auth-header "Bearer your-token" \
  --task "Your task here" \
  --agents "all"
```

## Output Format

The runner displays:
1. **Execution Summary Table** - Shows status, execution time, and errors for each agent
2. **Detailed Results** - Full output from each agent in formatted panels

## Agent Ports

Each agent uses a different OAuth callback port to avoid conflicts:
- Anthropic Agent: Port 3030
- Langchain Agent: Port 3031
- OpenAI Agent: Port 3032

## Error Handling

If a task cannot be completed:
- Agents will attempt to analyze the task first
- If incompletable, they'll report this before querying the MCP server
- Errors are displayed clearly in the results table

## License

MIT
