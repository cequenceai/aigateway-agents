# Slack Testing Setup

This guide is for **testing with Slack MCP server**. The system is generic, but this shows how to configure it for Slack testing.

## Quick Start (Slack Testing)

```bash
# Set your API keys
export ANTHROPIC_API_KEY="your-anthropic-key"
export OPENAI_API_KEY="your-openai-key"

# Set Slack MCP server
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"

# Set Slack channel ID for testing (DM channel)
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"

# Run in interactive mode
python3 agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --interactive
```

## One-Line Command (Slack Testing)

```bash
export ANTHROPIC_API_KEY="your-key" && \
export OPENAI_API_KEY="your-key" && \
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp" && \
export MCP_TARGET_IDENTIFIER="D025N5FN3RT" && \
python3 agent_runner.py --mcp-url "$MCP_SERVER_URL" --interactive
```

## Testing Different Agents

### Test Anthropic Agent Only
```bash
export ANTHROPIC_API_KEY="your-key"
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"

python3 agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --agents anthropic \
  --interactive
```

### Test Langchain Agent Only
```bash
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"

python3 agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --agents langchain \
  --interactive
```

### Test OpenAI Agent Only
```bash
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"

python3 agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --agents openai \
  --interactive
```

### Test All Agents in Parallel
```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"

python3 agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --agents anthropic langchain openai \
  --interactive
```

## Non-Interactive Mode (Slack Testing)

```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"

python3 agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --task "Send a message saying hello"
```

## What This Does

1. **Connects to Slack MCP server** - Uses the specified MCP URL
2. **Restricts to test channel** - All messages go to `D025N5FN3RT` (your DM channel)
3. **Maintains safety** - Prevents messaging other users/channels
4. **Works generically** - Same code works with any MCP server, just different config

## Notes

- The system is **generic** - it works with any MCP server
- For Slack testing, we set `MCP_TARGET_IDENTIFIER="D025N5FN3RT"`
- For other MCP servers, set `MCP_TARGET_IDENTIFIER` to their target ID
- If `MCP_TARGET_IDENTIFIER` is not set, agents use generic safety constraints

## Troubleshooting

**OAuth Issues:**
- The system will automatically handle OAuth if needed
- Follow the browser prompts to authorize

**Channel Not Found:**
- Verify `MCP_TARGET_IDENTIFIER` is set correctly
- Check that the channel ID exists in your Slack workspace

**Agent Not Responding:**
- Check API keys are set correctly
- Verify MCP server URL is accessible
- Check network connectivity
