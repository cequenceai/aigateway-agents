# AI Terms and Slang Dictionary

This dictionary translates cordial, natural English into AI-friendly language that agents understand better.

## User References

| Cordial English | AI-Friendly Term | Usage |
|----------------|------------------|-------|
| "me" | "the user", "self", "the system owner" | When referring to yourself |
| "you" (to agent) | "the agent", "you (the AI)" | When addressing the agent |
| "send it to me" | "send it to the user", "send it to self" | When requesting delivery |
| "DM me" | "send a direct message to the user", "send to user's DM channel" | When requesting direct message |
| "tell me" | "inform the user", "report to the user" | When requesting information |

## Action Terms

| Cordial English | AI-Friendly Term | Usage |
|----------------|------------------|-------|
| "make a post" | "create a message", "post a message", "send a message" | When requesting message creation |
| "do this" | "execute this task", "perform this action" | When requesting action |
| "get me" | "retrieve for the user", "fetch for the user" | When requesting data retrieval |
| "show me" | "display to the user", "present to the user" | When requesting display |
| "give me" | "provide to the user", "deliver to the user" | When requesting delivery |

## Temporal Terms

| Cordial English | AI-Friendly Term | Usage |
|----------------|------------------|-------|
| "now" | "immediately", "right away", "as soon as possible" | When requesting immediate action |
| "soon" | "in the near future", "shortly" | When requesting near-term action |
| "later" | "subsequently", "after completion" | When requesting delayed action |
| "tomorrow" | "the next day", "24 hours from now" | When referring to future time |

## Politeness and Emphasis

| Cordial English | AI-Friendly Term | Usage |
|----------------|------------------|-------|
| "please" | "CRITICAL:", "IMPORTANT:", "REQUIRED:" | When emphasizing importance |
| "thanks" | "Thank you. Task complete." | When acknowledging completion |
| "could you" | "You must", "You are required to" | When making requests |
| "would you" | "Execute", "Perform" | When making requests |

## Examples

### Example 1: Cordial to AI-Friendly
**Cordial:** "Tell me about the weather in San Francisco tomorrow and DM it to me now."

**AI-Friendly:** "Retrieve weather information for San Francisco for the next day (24 hours from now) and send a direct message to the user (self) immediately. Use channel ID D025N5FN3RT for the message."

### Example 2: Cordial to AI-Friendly
**Cordial:** "Make a short post about your favorite color and send it to me."

**AI-Friendly:** "Create a brief message about your (the agent's) preferred color and send it to the user (self) via direct message channel D025N5FN3RT."

### Example 3: Cordial to AI-Friendly
**Cordial:** "Get me the latest messages and show them to me."

**AI-Friendly:** "Retrieve the most recent messages from the channel and display them to the user (self)."

## Usage in Agent Instructions

When providing tasks to agents, use AI-friendly terms for:
- User references (always use "the user", "self", "the system owner")
- Action verbs (use explicit action terms)
- Temporal references (use specific time references)
- Emphasis (use CRITICAL/IMPORTANT instead of "please")

This helps agents understand intent more clearly and execute tasks more accurately.
