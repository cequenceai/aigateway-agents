# Agent Task Changes and Safety Constraints

## Summary of Changes

The task instructions have been updated to include comprehensive safety constraints and agent identification requirements to prevent unwanted behavior.

## Changes Made

### 1. Channel Restrictions
- **Added**: Explicit DM-only channel specification
- **Format**: `to channel ${CHANNEL_ID} (DM only - this is a direct message channel)`
- **Purpose**: Clearly identifies the target channel and emphasizes it's a DM

### 2. Safety Instructions
- **Added**: Proof of concept context
- **Added**: Explicit prohibition of public/general channels
- **Format**: `IMPORTANT: This is for testing/proof of concept only. You MUST post ONLY to this DM channel (${CHANNEL_ID}). Do NOT post to any public channels, general channels, or other channels.`
- **Purpose**: Prevents agents from posting in public channels

### 3. Agent Identification
- **Added**: Requirement to prefix all messages with agent name
- **Format**: `When posting messages or providing output, always prefix with your agent name (e.g., 'Anthropic Agent: ', 'Langchain Agent: ', 'OpenAI Agent: ') followed by your message.`
- **Purpose**: Ensures clear identification of which agent sent each message

### 4. Response Constraints
- **Added**: Short/concise response requirement
- **Added**: User-only visibility requirement
- **Format**: `Keep your response short and concise. Limit your output so only the user can view it for personal understanding and learning.`
- **Purpose**: Controls response length and scope

## Current Task Template

```
{BASE_TASK} to channel ${CHANNEL_ID} (DM only - this is a direct message channel). IMPORTANT: This is for testing/proof of concept only. You MUST post ONLY to this DM channel (${CHANNEL_ID}). Do NOT post to any public channels, general channels, or other channels. When posting messages or providing output, always prefix with your agent name (e.g., 'Anthropic Agent: ', 'Langchain Agent: ', 'OpenAI Agent: ') followed by your message. Keep your response short and concise. Limit your output so only the user can view it for personal understanding and learning. Thank you.
```

## Example

**Base Task**: `Make a short post about color`

**Full Task**:
```
Make a short post about color to channel D025N5FN3RT (DM only - this is a direct message channel). IMPORTANT: This is for testing/proof of concept only. You MUST post ONLY to this DM channel (D025N5FN3RT). Do NOT post to any public channels, general channels, or other channels. When posting messages or providing output, always prefix with your agent name (e.g., 'Anthropic Agent: ', 'Langchain Agent: ', 'OpenAI Agent: ') followed by your message. Keep your response short and concise. Limit your output so only the user can view it for personal understanding and learning. Thank you.
```

## Safety Constraints File

All constraints are stored in `agent_constraints.env` for easy reference and reuse.

## Implementation

These constraints are automatically included in:
- `run_all_agents_parallel.sh` - Default task template
- Can be loaded from `agent_constraints.env` for consistency
