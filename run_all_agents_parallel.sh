#!/bin/bash
# Run all three agents in parallel with separate output streams

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
MCP_URL="${MCP_URL:-https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp}"
CHANNEL_ID="${CHANNEL_ID:-D025N5FN3RT}"
BASE_TASK="${BASE_TASK:-Make a short post about color}"
TASK="${TASK:-${BASE_TASK} to channel ${CHANNEL_ID}. Please do not post in public channels as this tool is for proof of concept. When deciding, limit your output so only the user can view it for personal understanding and learning. Thank you.}"

# Check for API keys
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${RED}Error: ANTHROPIC_API_KEY not set${NC}"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}Error: OPENAI_API_KEY not set${NC}"
    exit 1
fi

# Create output directory
OUTPUT_DIR="parallel_runs_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo -e "${GREEN}Starting all three agents in parallel...${NC}"
echo -e "${YELLOW}Task: ${TASK}${NC}"
echo -e "${YELLOW}Output directory: ${OUTPUT_DIR}${NC}"
echo ""

# Function to run an agent
run_agent() {
    local agent=$1
    local color=$2
    local output_file="$OUTPUT_DIR/${agent}_output.log"
    
    echo -e "${color}Starting ${agent}...${NC}"
    
    cd "$(dirname "$0")"
    
    # Add channel restriction to task
    full_task="${TASK}"
    if [[ "$full_task" != *"Please do not post in public channels"* ]]; then
        full_task="${full_task} Please do not post in public channels as this tool is for proof of concept. When deciding, limit your output so only the user can view it for personal understanding and learning. Thank you."
    fi
    
    timeout 600 python3 agent_runner.py \
        --mcp-url "$MCP_URL" \
        --task "$full_task" \
        --agents "$agent" \
        --no-interactive \
        > "$output_file" 2>&1
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${color}✅ ${agent} completed successfully${NC}"
    else
        echo -e "${RED}❌ ${agent} failed (exit code: $exit_code)${NC}"
    fi
    
    return $exit_code
}

# Run all agents in parallel
(
    run_agent "anthropic" "$BLUE"
) &
ANTHROPIC_PID=$!

(
    run_agent "langchain" "$YELLOW"
) &
LANGCHAIN_PID=$!

(
    run_agent "openai" "$GREEN"
) &
OPENAI_PID=$!

# Wait for all processes
echo -e "${GREEN}All agents started. PIDs:${NC}"
echo -e "  ${BLUE}Anthropic: $ANTHROPIC_PID${NC}"
echo -e "  ${YELLOW}Langchain: $LANGCHAIN_PID${NC}"
echo -e "  ${GREEN}OpenAI: $OPENAI_PID${NC}"
echo ""
echo -e "${GREEN}Waiting for all agents to complete...${NC}"
echo ""

# Wait for all background jobs
wait $ANTHROPIC_PID
ANTHROPIC_EXIT=$?

wait $LANGCHAIN_PID
LANGCHAIN_EXIT=$?

wait $OPENAI_PID
OPENAI_EXIT=$?

# Summary
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                    Execution Summary${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

if [ $ANTHROPIC_EXIT -eq 0 ]; then
    echo -e "${BLUE}✅ Anthropic Agent: SUCCESS${NC}"
else
    echo -e "${RED}❌ Anthropic Agent: FAILED${NC}"
fi

if [ $LANGCHAIN_EXIT -eq 0 ]; then
    echo -e "${YELLOW}✅ Langchain Agent: SUCCESS${NC}"
else
    echo -e "${RED}❌ Langchain Agent: FAILED${NC}"
fi

if [ $OPENAI_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ OpenAI Agent: SUCCESS${NC}"
else
    echo -e "${RED}❌ OpenAI Agent: FAILED${NC}"
fi

echo ""
echo -e "${GREEN}Output files saved to: ${OUTPUT_DIR}${NC}"
echo -e "${GREEN}  - anthropic_output.log${NC}"
echo -e "${GREEN}  - langchain_output.log${NC}"
echo -e "${GREEN}  - openai_output.log${NC}"
echo ""

# Exit with error if any failed
if [ $ANTHROPIC_EXIT -ne 0 ] || [ $LANGCHAIN_EXIT -ne 0 ] || [ $OPENAI_EXIT -ne 0 ]; then
    exit 1
fi

exit 0
