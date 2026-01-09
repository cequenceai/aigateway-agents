#!/bin/bash
# Test script for interactive mode
# Run this in your terminal: ./test_interactive.sh

cd "/Users/abhinav/Desktop/Cequence. /three_agents"

echo "=== Interactive Mode Test ==="
echo ""
echo "This will run the agent runner in interactive mode."
echo "You will be prompted for:"
echo "  1. Task to execute"
echo "  2. Agent selection (anthropic, langchain, openai, or 'all')"
echo ""
echo "Starting interactive session..."
echo ""

python3 agent_runner.py --mcp-url "https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp"
