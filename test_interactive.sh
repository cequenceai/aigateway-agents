#!/bin/bash
# Test script for interactive mode

cd "$(dirname "$0")"

export ANTHROPIC_API_KEY='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'
export OPENAI_API_KEY='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'

echo "=== Interactive Mode Test ==="
echo ""
echo "This will run in interactive mode."
echo "When prompted, enter:"
echo "  Task: Tell me your favorite color by dming me Abhinav Allam"
echo "  Agents: 1 (or 'all')"
echo ""

python3 agent_runner.py --mcp-url 'https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp'
