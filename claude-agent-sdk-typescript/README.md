# MCP Agent - Claude Agent SDK (TypeScript)

Interactive terminal agent that connects to MCP servers using the Claude Agent SDK. Supports OAuth 2.1 with PKCE for secure authentication.

## Prerequisites

- Node.js 18+
- `ANTHROPIC_API_KEY` environment variable set

## Installation

```bash
cd claude-agent-sdk-typescript
npm install
```

## Usage

### Basic usage (with automatic OAuth + PKCE if required)

```bash
ANTHROPIC_API_KEY="your-key" npx tsx src/index.ts --mcp-url https://your-mcp-server.com/mcp
```

### With static auth token

```bash
ANTHROPIC_API_KEY="your-key" npx tsx src/index.ts --mcp-url https://your-mcp-server.com/mcp --auth-token "Bearer your-token"
```

### Disable OAuth (for local servers without auth)

```bash
ANTHROPIC_API_KEY="your-key" npx tsx src/index.ts --mcp-url http://localhost:8000/mcp --no-oauth
```

### Use a specific model

```bash
ANTHROPIC_API_KEY="your-key" npx tsx src/index.ts --mcp-url https://your-mcp-server.com/mcp --model claude-sonnet-4-20250514
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--mcp-url <url>` | MCP server URL (required) |
| `--auth-token <token>` | Authorization token (Bearer token) |
| `--no-oauth` | Disable automatic OAuth flow |
| `--model <model>` | Claude model to use (default: claude-sonnet-4-20250514) |
| `--help` | Show help message |

## Chat Commands

| Command | Description |
|---------|-------------|
| `/quit`, `/exit`, `/q` | Exit the chat |
| `/clear` | Clear conversation history |
| `/help` | Show available commands |

## Architecture

```
src/
├── index.ts           # CLI entry point and chat loop
├── auth/
│   └── oauth.ts       # OAuth 2.1 with PKCE support
└── agent/
    └── mcp-agent.ts   # Agent configuration and query execution
```

## Features

### OAuth 2.1 with PKCE

The agent implements the full OAuth 2.1 flow with PKCE (Proof Key for Code Exchange):

1. **Discovery** - Fetches OAuth metadata from `/.well-known/oauth-authorization-server`
2. **Dynamic Client Registration** - Registers client if endpoint available
3. **PKCE** - Generates `code_verifier` and `code_challenge` (SHA-256)
4. **Browser Auth** - Opens browser for user authentication
5. **Callback Server** - Local server on port 3030 captures the callback
6. **Token Exchange** - Exchanges auth code + code verifier for access token

### MCP Tool Access

MCP server tools are automatically discovered and made available to the agent. Tools follow the naming convention `mcp__<server-name>__<tool-name>`.

The agent logs:
- MCP server connection status
- Available MCP tools

## Comparison with LangGraph Implementation

| Feature | LangGraph (Python) | Claude Agent SDK (TypeScript) |
|---------|-------------------|-------------------------------|
| MCP Client | `MultiServerMCPClient` | Built-in MCP server support |
| Agent Loop | Manual `create_agent()` + `ainvoke()` | Automatic via `query()` |
| Tool Discovery | Explicit `get_tools()` | Automatic |
| OAuth | Manual `OAuthClientProvider` | Custom implementation with PKCE |
| Tool Permissions | Automatic | Via `allowedTools` option |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required. Your Anthropic API key |

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI (index.ts)                          │
│  - Argument parsing                                         │
│  - OAuth flow orchestration                                 │
│  - Interactive chat loop                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
    ┌────────────────┴──────────────┐
    │                               │
    v                               v
┌────────────────────┐  ┌──────────────────────┐
│  agent/mcp-agent   │  │  auth/oauth.ts       │
│                    │  │                      │
│ - query() wrapper  │  │ - PKCE generation    │
│ - MCP server config│  │ - Callback server    │
│ - Message handling │  │ - Token exchange     │
│ - Tool logging     │  │ - Browser open       │
└────────┬───────────┘  └──────────────────────┘
         │
         v
┌────────────────────────────────────┐
│ Claude Agent SDK                    │
│ - Automatic tool orchestration      │
│ - MCP server connection             │
│ - Streaming message handling        │
└────────────────────────────────────┘
```
