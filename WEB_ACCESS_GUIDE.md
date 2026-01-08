# Web Access Guide for Agents

## Overview

Both **Langchain** and **OpenAI** agents can access web search and browsing capabilities. This guide explains how web access works and how to enable it.

## Current State

### MCP Server Tools (Already Available)

Your MCP server already provides web tools:
- **WebFetch** - Fetch and analyze web content
- **WebSearch** - Search the web (US only, includes sources)

These tools are **automatically available** to both Langchain and OpenAI agents when they connect to the MCP server.

### Additional Web Tools (Optional)

You can add additional web search tools beyond what the MCP server provides:

#### For Langchain Agent

The Langchain agent now supports additional web search tools:

1. **DuckDuckGo Search** (No API key required)
   - Free, privacy-focused search
   - Automatically added if `duckduckgo-search` is installed

2. **Tavily Search** (Requires API key)
   - AI-optimized search API
   - Requires `TAVILY_API_KEY` environment variable
   - Automatically added if `langchain-community` is installed and API key is set

## Installation

### Install Web Search Packages

```bash
cd three_agents/langchain_agent
pip install duckduckgo-search langchain-community
```

### Optional: Set Tavily API Key

If you want to use Tavily search (better quality, requires API key):

```bash
export TAVILY_API_KEY="your-tavily-api-key-here"
```

Get a free API key at: https://tavily.com

## How It Works

### Langchain Agent

1. **MCP Tools**: Automatically loaded from MCP server (WebFetch, WebSearch)
2. **Additional Tools**: DuckDuckGo and/or Tavily are added if available
3. **Combined**: All tools are available to the agent

### OpenAI Agent

- **MCP Tools Only**: Gets tools from MCP server (WebFetch, WebSearch)
- The OpenAI Agents SDK automatically discovers and uses all MCP server tools

## Usage Examples

### Example 1: Search the Web

```
Task: "Search for the latest news about AI agents and summarize the top 3 results"
```

The agent will use:
- WebSearch (from MCP server) OR
- DuckDuckGoSearchRun (if installed) OR
- TavilySearchResults (if API key is set)

### Example 2: Fetch Web Content

```
Task: "Fetch and summarize the content from https://example.com/article"
```

The agent will use:
- WebFetch (from MCP server)

## Verification

To verify web access is working:

```bash
# Run with a web search task
python3 agent_runner.py \
  --mcp-url "https://your-mcp-server.com/mcp" \
  --task "Search for 'LangChain web search tools' and summarize the results" \
  --agents "langchain"
```

You should see:
- ✓ Loaded X tool(s) from MCP server
- ✓ Added DuckDuckGo web search tool (if installed)
- ✓ Added Tavily web search tool (if API key is set)

## Troubleshooting

### Web tools not appearing

1. **Check MCP server**: Ensure your MCP server provides WebFetch/WebSearch tools
2. **Check installation**: Run `pip list | grep duckduckgo` to verify packages
3. **Check API keys**: For Tavily, ensure `TAVILY_API_KEY` is set
4. **Check logs**: Look for "✓ Added" messages in agent startup logs

### Import errors

If you see import errors:
```bash
pip install duckduckgo-search langchain-community
```

### Tool conflicts

If multiple web search tools are available, the agent will choose the most appropriate one based on the task.

## Notes

- **MCP Tools**: Always available if MCP server provides them
- **DuckDuckGo**: Free, no API key needed, good for general search
- **Tavily**: Requires API key, better quality for AI applications
- **OpenAI Agent**: Uses MCP tools only (no additional tools can be added currently)

## Future Enhancements

Potential additions:
- Browser automation tools (Playwright, Selenium)
- Custom web scraping tools
- RSS feed readers
- Social media search tools
