# Project Summary - Unified Agent Runner

## Overview

This project implements a **unified CLI interface** for running tasks across three different AI agent SDKs (Anthropic, Langchain, OpenAI) using a single MCP (Model Context Protocol) server. The system allows users to execute the same task across multiple agents simultaneously or individually, with interactive prompting and safety constraints.

## What's Been Done

### 1. Unified Agent Runner (`agent_runner.py`)
- **Multi-agent support**: Run tasks across Anthropic, Langchain, and OpenAI agents
- **Interactive mode**: Users can provide tasks and select agents interactively
- **Parallel execution**: All agents run simultaneously with round-robin input queue
- **Single agent mode**: Agents wait for user input before/during execution
- **Progress tracking**: Real-time status updates and timing information
- **KPI tracking**: Metrics for tool calls, message delivery, safety compliance

### 2. Safety and Code of Conduct
- **Principle-based Code of Conduct**: 5 core principles (Least Privilege, Caution, Scope Limitation, Explicit Permission, Minimal Impact)
- **Messaging restrictions**: Explicit instructions to ONLY use channel ID `D025N5FN3RT` (Slack DM channel)
- **No user search**: Agents explicitly prohibited from searching for or messaging random users
- **No profile creation**: Agents cannot create users, profiles, or guest accounts
- **Critical warnings**: Code comments warn that AI agents will try to DM everyone if not restricted

### 3. Interactive Prompting
- **Single agent**: Program waits for user input before/during execution
- **Parallel execution**: Round-robin queue system - agents request input, first-come-first-served
- **Background execution**: Agents continue running while waiting for input
- **User-friendly prompts**: Clear prompts showing which agent is requesting input

### 4. User Reference Instructions
- **Translation system**: "me"/"I" → "the user"/"self"/"system owner"
- **AI Terms Dictionary**: Comprehensive dictionary translating cordial English to AI-friendly language
- **Explicit instructions**: All agents understand user references correctly

### 5. Temperature Control
- **Command-line argument**: `--temperature` (0.0-2.0)
- **Anthropic Agent**: Temperature support via `ClaudeAgentOptions`
- **OpenAI Agent**: Temperature support via `Agent` constructor
- **Langchain Agent**: Depends on SDK version (may vary)

### 6. Documentation
- **INTERACTIVE_MODE_GUIDE.md**: Detailed usage guide with Slack and generic examples
- **QUICK_START.md**: 5-minute onboarding guide
- **AI_TERMS_DICTIONARY.md**: Translation dictionary for AI-friendly language
- **AGENT_CODE_OF_CONDUCT.md**: Principle-based safety guidelines

## Systems Architecture

### Agent Execution Flow

```
User Input (Task)
    ↓
Agent Selection (Anthropic/Langchain/OpenAI)
    ↓
┌─────────────────────────────────────┐
│  Single Agent Mode                 │
│  - Waits for user input             │
│  - Executes task                    │
│  - Shows results                    │
└─────────────────────────────────────┘
           OR
┌─────────────────────────────────────┐
│  Parallel Mode (Multiple Agents)    │
│  - All agents start simultaneously  │
│  - Round-robin input queue          │
│  - Background execution             │
│  - Results aggregated               │
└─────────────────────────────────────┘
```

### Round-Robin Input Queue System

When multiple agents run in parallel:
1. Agents execute in background
2. When an agent needs input, it adds itself to the queue
3. Input handler processes queue requests sequentially (first-come-first-served)
4. User responds to each agent as they request input
5. Agents continue execution after receiving input

### OAuth Authentication Flow

**⚠️ IMPORTANT: Temporary Refresh Tokens**

The system uses OAuth 2.0 for MCP server authentication. This involves:

1. **Temporary Refresh Tokens**: OAuth tokens are stored temporarily in memory (`InMemoryTokenStorage`)
2. **Token Expiration**: Tokens expire and need to be refreshed
3. **Browser OAuth Flow**: Automatically opens browser for authentication
4. **Callback Server**: Local server (ports 3030, 3031, 3032) receives OAuth callbacks
5. **Token Storage**: Tokens are NOT persisted - they are temporary and session-based

**When Switching Accounts:**
- OAuth tokens are session-specific
- Each new session requires re-authentication
- Browser will open for OAuth flow again
- Previous tokens are not reused

**Ports Used:**
- Anthropic Agent: Port 3030
- Langchain Agent: Port 3031
- OpenAI Agent: Port 3032

## Key Decisions Made

### 1. Safety-First Approach
**Decision**: Implement strict safety constraints and Code of Conduct
**Rationale**: AI agents will naturally try to explore and interact broadly. Without explicit restrictions, they will message random users, create entities, and take unwanted actions.
**Implementation**: 
- Principle-based Code of Conduct (not exhaustive list)
- Explicit channel restrictions (D025N5FN3RT only)
- Code comments warning about agent behavior
- Multiple layers of safety instructions

### 2. Interactive Prompting System
**Decision**: Implement round-robin queue for parallel execution, blocking prompts for single agents
**Rationale**: 
- Single agents: User needs time to provide input
- Parallel agents: Need fair access to user input without blocking each other
**Implementation**:
- `asyncio.Queue` for input requests
- Background input handler task
- First-come-first-served processing

### 3. User Reference Translation
**Decision**: Translate "me"/"I" to "the user"/"self" in instructions
**Rationale**: AI agents interpret pronouns differently. Explicit user references improve understanding.
**Implementation**: 
- User reference instructions in all agent prompts
- AI Terms Dictionary for comprehensive translation
- Examples showing cordial → AI-friendly translations

### 4. Temperature Control
**Decision**: Add temperature parameter with graceful fallback
**Rationale**: Different tasks may benefit from different creativity levels (temperature)
**Implementation**:
- Command-line argument `--temperature`
- Try/except blocks for SDK compatibility
- Defaults to model defaults if not supported

### 5. Sanitized vs Slack-Specific
**Decision**: Keep Slack-specific restrictions (D025N5FN3RT) but structure code generically
**Rationale**: 
- Current use case is Slack-specific
- Code structure supports any MCP server
- Can be generalized later if needed
**Implementation**:
- Channel ID hardcoded in instructions (Slack-specific)
- MCP server URL is generic (works with any server)
- Code structure is MCP-server agnostic

## File Structure

```
three_agents/
├── agent_runner.py              # Main unified CLI
├── agent_constraints.env        # Safety constraints configuration
├── AGENT_CODE_OF_CONDUCT.md     # Principle-based safety guidelines
├── AI_TERMS_DICTIONARY.md       # Translation dictionary
├── INTERACTIVE_MODE_GUIDE.md    # Detailed usage guide
├── QUICK_START.md               # Quick start guide
├── PROJECT_SUMMARY.md           # This file
├── anthropic_agent/             # Anthropic agent implementation
├── langchain_agent/             # Langchain agent implementation
└── openai_agent/                # OpenAI agent implementation
```

## Important Notes

### OAuth Tokens (Temporary)
- **Temporary**: Tokens are stored in memory only (`InMemoryTokenStorage`)
- **Session-based**: Tokens expire when session ends
- **Re-authentication**: Required for each new session
- **Browser flow**: OAuth flow opens browser automatically
- **No persistence**: Tokens are NOT saved to disk

### Channel Restrictions
- **Slack-specific**: Channel ID `D025N5FN3RT` is hardcoded
- **No exceptions**: Agents MUST use this channel only
- **No user search**: Agents cannot search for users
- **DM-only**: All messages go to this DM channel

### Agent Behavior Warnings
- **Code comments**: Explicit warnings that agents will DM everyone if not restricted
- **Multiple layers**: Restrictions in Code of Conduct, task instructions, and code comments
- **Explicit is required**: Assumptions are not safe - everything must be explicit

## Usage Examples

### Single Agent (Interactive)
```bash
python3 agent_runner.py --mcp-url 'https://your-server.com/mcp'
# Program waits for your input before/during execution
```

### Multiple Agents (Parallel)
```bash
python3 agent_runner.py --mcp-url 'https://your-server.com/mcp'
# Select multiple agents (e.g., "all" or "1,2,3")
# Agents run in parallel with round-robin input queue
```

### With Temperature Control
```bash
python3 agent_runner.py --mcp-url 'https://your-server.com/mcp' --temperature 0.7
```

## Next Steps / TODO

1. **Generalize channel restrictions**: Make channel ID configurable via environment variable
2. **Token persistence**: Option to persist OAuth tokens (with user consent)
3. **Enhanced error handling**: Better error messages and recovery
4. **Agent comparison**: Side-by-side comparison of agent outputs
5. **Task templates**: Pre-defined task templates for common operations

## Switching Accounts

When switching accounts or starting a new session:

1. **OAuth tokens are temporary** - They expire and are not persisted
2. **Re-authentication required** - Browser will open for OAuth flow
3. **Previous tokens invalid** - Cannot reuse tokens from previous session
4. **Fresh start** - Each session starts with new authentication

**This is by design** - Tokens are intentionally temporary for security. If you need persistent authentication, consider implementing token storage (with proper security measures).

## Support

For issues or questions:
- Check `INTERACTIVE_MODE_GUIDE.md` for detailed usage
- Check `QUICK_START.md` for quick reference
- Review `AGENT_CODE_OF_CONDUCT.md` for safety principles
- See `AI_TERMS_DICTIONARY.md` for language translation help
