# Branch Structure

This repository uses separate branches for each agent implementation to allow independent development and deployment.

## Agent Branches

### `agent/anthropic`
- **Purpose**: Anthropic Claude Agent SDK implementation
- **Files**: 
  - `anthropic_agent/` directory
  - `agent_runner.py` (unified runner)
  - Shared configuration files

### `agent/langchain`
- **Purpose**: Langchain Agent with MCP integration
- **Files**:
  - `langchain_agent/` directory
  - `agent_runner.py` (unified runner)
  - Shared configuration files

### `agent/openai`
- **Purpose**: OpenAI Agents SDK implementation
- **Files**:
  - `openai_agent/` directory
  - `agent_runner.py` (unified runner)
  - Shared configuration files

## Main Branch

`three-agents-examples-merged` - Contains all three agents together for unified testing and deployment.

## Usage

Each branch can be developed and deployed independently:

```bash
# Work on Anthropic agent
git checkout agent/anthropic
# Make changes to anthropic_agent/
git add anthropic_agent/
git commit -m "Update Anthropic agent"
git push

# Work on Langchain agent
git checkout agent/langchain
# Make changes to langchain_agent/
git add langchain_agent/
git commit -m "Update Langchain agent"
git push

# Work on OpenAI agent
git checkout agent/openai
# Make changes to openai_agent/
git add openai_agent/
git commit -m "Update OpenAI agent"
git push
```

## Creating Pull Requests

Create separate PRs for each agent branch:
- `agent/anthropic` → `main`
- `agent/langchain` → `main`
- `agent/openai` → `main`

This allows independent review and merging of each agent implementation.
