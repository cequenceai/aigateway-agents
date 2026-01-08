# Running Agents in Parallel

Two scripts are available to run all three agents simultaneously:

## Option 1: Parallel with Separate Output Files (Recommended)

Runs all agents in parallel in the same terminal, but saves output to separate log files:

```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export TASK="Make a post about color using the MCP server tools"  # Optional
export MCP_URL="https://your-mcp-server.com/mcp"  # Optional

./run_all_agents_parallel.sh
```

**Output:**
- Creates a timestamped directory (e.g., `parallel_runs_20260107_210000/`)
- Each agent's output saved to separate log files:
  - `anthropic_output.log`
  - `langchain_output.log`
  - `openai_output.log`

## Option 2: Separate Terminal Windows (macOS)

Launches each agent in its own Terminal window:

```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export TASK="Make a post about color using the MCP server tools"  # Optional
export MCP_URL="https://your-mcp-server.com/mcp"  # Optional

./run_agents_separate_terminals.sh
```

**Output:**
- Opens 3 new Terminal windows
- Each window shows one agent's execution
- Agents run completely independently

## Customization

Both scripts support environment variables:
- `TASK` - The task to execute (default: "Make a post about color using the MCP server tools")
- `MCP_URL` - MCP server URL (default: Slack MCP server)
- `ANTHROPIC_API_KEY` - Required
- `OPENAI_API_KEY` - Required
- `OPENAI_MODEL` - Optional (default: gpt-4o)

## Example

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."
export TASK="List all available tools from the MCP server"
./run_all_agents_parallel.sh
```
