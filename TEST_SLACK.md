# Testing with Slack MCP Server

## Quick Test Command

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export OPENAI_API_KEY="your-openai-key"
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"

cd three_agents
python agent_runner.py --interactive
```

## Test All Three Agents

```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export MCP_SERVER_URL="https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"
export MCP_TARGET_IDENTIFIER="D025N5FN3RT"

python agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --agents all \
  --task "Send a test message saying hello"
```

## Test Individual Agents

### Anthropic Only
```bash
python agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --agents anthropic \
  --task "List available tools"
```

### Langchain Only
```bash
python agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --agents langchain \
  --task "List available tools"
```

### OpenAI Only
```bash
python agent_runner.py \
  --mcp-url "$MCP_SERVER_URL" \
  --agents openai \
  --task "List available tools"
```

## Expected Behavior

### Langchain Agent
- **Connection**: Should complete in < 30 seconds (timeout protection)
- **Tool Discovery**: Should complete in < 30 seconds
- **Task Execution**: Should complete in < 60 seconds
- **Total Time**: Should be < 2 minutes (vs. previous 5+ minutes)

### All Agents
- Should discover MCP tools automatically
- Should be able to send messages to D025N5FN3RT
- Should prefix messages with agent name
- Should complete tasks successfully

## Troubleshooting

### Langchain Taking Too Long
- Check timeout values in `langchain_agent/agent/graph.py` (30s for get_tools)
- Check timeout in `agent_runner.py` (120s for full session)
- Verify MCP server is responsive

### Connection Timeouts
- Verify MCP server URL is correct
- Check network connectivity
- Try with `--auth-header` if OAuth is failing

### Agent Not Responding
- Check API keys are set correctly
- Verify agent is selected
- Check error messages in output
