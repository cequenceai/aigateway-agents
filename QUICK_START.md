# Quick Start Guide

Get started with the Unified Agent Runner in 5 minutes.

## Prerequisites

- Python 3.7+
- API keys for at least one provider:
  - Anthropic API key (for Anthropic Agent)
  - OpenAI API key (for OpenAI Agent and Langchain Agent)

## Installation

```bash
cd three_agents
pip install -r requirements.txt
```

## Basic Usage

### 1. Set API Keys

```bash
export ANTHROPIC_API_KEY='your-anthropic-key-here'
export OPENAI_API_KEY='your-openai-key-here'
export OPENAI_MODEL='gpt-4o'  # Optional
```

### 2. Run Interactive Mode

```bash
python3 agent_runner.py --mcp-url 'https://your-mcp-server.com/mcp'
```

### 3. Enter Your Task

When prompted:
- Type your task (e.g., "List available tools")
- Select which agents to use (1, 2, 3, or 'all')
- Watch the agents execute and see results

## Example: Slack MCP Server

```bash
# Set API keys
export ANTHROPIC_API_KEY='your-key'
export OPENAI_API_KEY='your-key'
export OPENAI_MODEL='gpt-4o'

# Run with Slack MCP server
python3 agent_runner.py --mcp-url 'https://your-slack-mcp-server.com/mcp'
```

**Task Example:**
```
Task: Send me a message saying hello
Agents: 3
```

**Note:** All messages automatically go to channel `D025N5FN3RT` (your DM channel).

## Example: Generic MCP Server

```bash
# Set API keys
export ANTHROPIC_API_KEY='your-key'
export OPENAI_API_KEY='your-key'

# Run with any MCP server
python3 agent_runner.py --mcp-url 'https://your-mcp-server.com/mcp'
```

**Task Examples:**
- "List all available tools"
- "Get the current system status"
- "Retrieve and summarize the latest data"

## Non-Interactive Mode

For automation:

```bash
python3 agent_runner.py \
  --mcp-url 'https://your-mcp-server.com/mcp' \
  --task "Your task here" \
  --agents "anthropic,openai" \
  --no-interactive
```

## What You'll See

1. **Task Analysis**: Shows how agents will interpret your task
2. **Progress Updates**: Real-time status from each agent
3. **Execution Summary**: Table with results from all agents
4. **KPIs**: Key performance indicators for each agent
5. **Timing Log**: Detailed log saved to `agent_timing_log_*.md`

## Safety

- Agents follow a strict Code of Conduct
- For Slack: All messages restricted to channel `D025N5FN3RT`
- No user search, no profile creation, no unwanted actions
- See `AGENT_CODE_OF_CONDUCT.md` for details

## Next Steps

- Read `INTERACTIVE_MODE_GUIDE.md` for detailed usage
- Check `README_RUNNER.md` for advanced features
- Review `AGENT_CODE_OF_CONDUCT.md` for safety principles

## Troubleshooting

**No agents available?**
- Make sure at least one API key is set
- Check that the API key is valid

**OAuth not working?**
- Complete the browser OAuth flow
- Check network connectivity

**Agent timeout?**
- Try breaking tasks into smaller steps
- Check MCP server response times

## Support

For issues or questions, check the documentation files:
- `INTERACTIVE_MODE_GUIDE.md` - Detailed usage guide
- `README_RUNNER.md` - Full feature documentation
- `AGENT_CODE_OF_CONDUCT.md` - Safety principles
