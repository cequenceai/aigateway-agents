#!/bin/bash
# Run each agent in a separate terminal window (macOS)

set -e

# Configuration
MCP_URL="${MCP_URL:-https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp}"
TASK="${TASK:-Make a post about color using the MCP server tools}"

# Check for API keys
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY not set"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY not set"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Launching agents in separate terminal windows..."
echo "Task: $TASK"
echo ""

# Launch Anthropic Agent in new terminal
osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR' && export ANTHROPIC_API_KEY='$ANTHROPIC_API_KEY' && export OPENAI_API_KEY='$OPENAI_API_KEY' && export OPENAI_MODEL='gpt-4o' && python3 agent_runner.py --mcp-url '$MCP_URL' --task '$TASK' --agents 'anthropic' --no-interactive\""

sleep 1

# Launch Langchain Agent in new terminal
osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR' && export ANTHROPIC_API_KEY='$ANTHROPIC_API_KEY' && export OPENAI_API_KEY='$OPENAI_API_KEY' && export OPENAI_MODEL='gpt-4o' && python3 agent_runner.py --mcp-url '$MCP_URL' --task '$TASK' --agents 'langchain' --no-interactive\""

sleep 1

# Launch OpenAI Agent in new terminal
osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR' && export ANTHROPIC_API_KEY='$ANTHROPIC_API_KEY' && export OPENAI_API_KEY='$OPENAI_API_KEY' && export OPENAI_MODEL='gpt-4o' && python3 agent_runner.py --mcp-url '$MCP_URL' --task '$TASK' --agents 'openai' --no-interactive\""

echo "✅ All three agents launched in separate terminal windows"
echo ""
echo "Each agent is running independently. Check the terminal windows for output."
