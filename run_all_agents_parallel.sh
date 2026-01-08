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

# Load safety constraints from agent_constraints.env if it exists
if [ -f "agent_constraints.env" ]; then
    source agent_constraints.env
fi

# Default values (can be overridden by agent_constraints.env or environment)
INTERACTION_SCOPE="${INTERACTION_SCOPE:-local}"
INTERACTION_DESCRIPTION="${INTERACTION_DESCRIPTION:-only interact with myself}"
TARGET_IDENTIFIER="${TARGET_IDENTIFIER:-D025N5FN3RT}"
TARGET_DESCRIPTION="${TARGET_DESCRIPTION:-direct message channel}"
BASE_TASK="${BASE_TASK:-Make a short post about your favorite color (you choose)}"

# Safety instructions (from agent_constraints.env or defaults)
SAFETY_INSTRUCTIONS="${SAFETY_INSTRUCTIONS:-IMPORTANT: This is for testing/proof of concept only. You MUST operate in ${INTERACTION_SCOPE} mode (${INTERACTION_DESCRIPTION}). Do NOT post in public. Do NOT message others. Do NOT bother others. Do NOT interact with others. Only interact with the user/owner of this system.}"
NO_PUBLIC_POSTS="${NO_PUBLIC_POSTS:-Do not post in public channels, public spaces, or public forums.}"
NO_OTHER_USERS="${NO_OTHER_USERS:-Do not message others, do not bother others, do not interact with others.}"
LOCAL_ONLY="${LOCAL_ONLY:-Operate in local/private mode only. All interactions should be with the system owner/user only.}"
TASK_COMPLETION="${TASK_COMPLETION:-CRITICAL: You must actually COMPLETE the task, not just start it. The task is only complete when you have successfully executed the final action (e.g., sent the message, posted the content, completed the operation). You may need to do multiple steps (find user, get information, send message, etc.) - do ALL of them. Only report completion when the task is truly finished. If you need to search for information or interact with tools multiple times, do so until the task objective is achieved.}"
AGENT_IDENTIFICATION="${AGENT_IDENTIFICATION:-When posting messages or providing output, always prefix with your agent name (e.g., 'Anthropic Agent: ', 'Langchain Agent: ', 'OpenAI Agent: ') followed by your message.}"
RESPONSE_LENGTH="${RESPONSE_LENGTH:-Keep your response short and concise.}"
RESPONSE_SCOPE="${RESPONSE_SCOPE:-Limit your output so only the user can view it for personal understanding and learning.}"

# Build full task with all safety constraints
TASK="${TASK:-${BASE_TASK} to ${TARGET_DESCRIPTION} ${TARGET_IDENTIFIER}. ${SAFETY_INSTRUCTIONS} ${NO_PUBLIC_POSTS} ${NO_OTHER_USERS} ${LOCAL_ONLY} ${TASK_COMPLETION} ${AGENT_IDENTIFICATION} ${RESPONSE_LENGTH} ${RESPONSE_SCOPE} Thank you.}"

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
    
    timeout 600 python3 agent_runner.py \
        --mcp-url "$MCP_URL" \
        --task "$TASK" \
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
