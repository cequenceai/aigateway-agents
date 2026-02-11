/**
 * MCP Agent configuration and session management using Claude Agent SDK.
 */

import { query, type Options, type McpHttpServerConfig, type SDKMessage } from "@anthropic-ai/claude-agent-sdk";

export interface AgentConfig {
  mcpUrl: string;
  authToken?: string;
  model?: string;
}

/**
 * Create MCP server configuration for the Claude Agent SDK
 */
export function createMcpServerConfig(config: AgentConfig): Options["mcpServers"] {
  const serverConfig: McpHttpServerConfig = {
    type: "http",
    url: config.mcpUrl,
  };

  // Add authorization header if token provided
  if (config.authToken) {
    serverConfig.headers = {
      Authorization: config.authToken.startsWith("Bearer ")
        ? config.authToken
        : `Bearer ${config.authToken}`,
    };
  }

  return {
    "mcp-server": serverConfig,
  };
}

/**
 * Extract text content from an SDK message
 */
function extractMessageContent(message: SDKMessage): string {
  if (message.type === "assistant") {
    // SDKAssistantMessage has a `message` property containing the API response
    const apiMessage = message.message;
    if (apiMessage && apiMessage.content) {
      if (typeof apiMessage.content === "string") {
        return apiMessage.content;
      }
      if (Array.isArray(apiMessage.content)) {
        const textBlocks = apiMessage.content.filter(
          (block: { type: string }): block is { type: "text"; text: string } =>
            block.type === "text"
        );
        return textBlocks.map((block: { type: "text"; text: string }) => block.text).join("");
      }
    }
  } else if (message.type === "result") {
    // SDKResultMessage has a `result` property only on success subtype
    if (message.subtype === "success") {
      return message.result || "";
    }
  }
  return "";
}

/**
 * Run a single query against the MCP server
 */
export async function runQuery(
  prompt: string,
  config: AgentConfig,
  conversationHistory: Array<{ role: string; content: string }> = []
): Promise<string> {
  const mcpServers = createMcpServerConfig(config);

  // Build the full prompt with conversation history
  let fullPrompt = prompt;
  if (conversationHistory.length > 0) {
    const historyText = conversationHistory
      .map((msg) => `${msg.role}: ${msg.content}`)
      .join("\n");
    fullPrompt = `Previous conversation:\n${historyText}\n\nUser: ${prompt}`;
  }

  const options: Options = {
    mcpServers,
    model: config.model || "claude-sonnet-4-20250514",
    permissionMode: "acceptEdits",
    // Allow all tools from the MCP server (mcp__<server-name>__<tool-name>)
    allowedTools: ["mcp__mcp-server__*"],
  };

  let response = "";

  try {
    const messages = query({ prompt: fullPrompt, options });

    for await (const message of messages) {
      // Log system init message to show MCP server status
      if (message.type === "system" && "subtype" in message && message.subtype === "init") {
        const initMessage = message as { mcp_servers?: Array<{ name: string; status: string }>; tools?: string[] };
        if (initMessage.mcp_servers) {
          console.log("\n[MCP Servers]");
          for (const server of initMessage.mcp_servers) {
            const statusIcon = server.status === "connected" ? "✓" : "✗";
            console.log(`  ${statusIcon} ${server.name}: ${server.status}`);
          }
        }
        if (initMessage.tools) {
          const mcpTools = initMessage.tools.filter((t: string) => t.startsWith("mcp__"));
          if (mcpTools.length > 0) {
            console.log("\n[MCP Tools Available]");
            for (const tool of mcpTools) {
              console.log(`  • ${tool}`);
            }
          }
        }
        console.log();
      }

      if (message.type === "assistant") {
        const content = extractMessageContent(message);
        if (content) {
          response = content;
        }

        // Log tool usage if present
        const apiMessage = message.message;
        if (apiMessage && apiMessage.content && Array.isArray(apiMessage.content)) {
          for (const block of apiMessage.content) {
            if (block.type === "tool_use") {
              console.log(`\n[Tool Call] ${block.name}`);
              console.log(`  Args: ${JSON.stringify(block.input, null, 2)}`);
            }
          }
        }
      } else if (message.type === "result") {
        // Final result message
        const resultContent = extractMessageContent(message);
        if (resultContent) {
          response = resultContent;
        }
      }
    }
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`Agent query failed: ${error.message}`);
    }
    throw error;
  }

  return response;
}

/**
 * Stream a query and yield responses as they come
 */
export async function* streamQuery(
  prompt: string,
  config: AgentConfig
): AsyncGenerator<{ type: string; content: string }> {
  const mcpServers = createMcpServerConfig(config);

  const options: Options = {
    mcpServers,
    model: config.model || "claude-sonnet-4-20250514",
    permissionMode: "acceptEdits",
    // Allow all tools from the MCP server (mcp__<server-name>__<tool-name>)
    allowedTools: ["mcp__mcp-server__*"],
  };

  const messages = query({ prompt, options });

  for await (const message of messages) {
    if (message.type === "assistant") {
      const content = extractMessageContent(message);
      if (content) {
        yield { type: "assistant", content };
      }

      // Yield tool calls
      const apiMessage = message.message;
      if (apiMessage && apiMessage.content && Array.isArray(apiMessage.content)) {
        for (const block of apiMessage.content) {
          if (block.type === "tool_use") {
            yield {
              type: "tool_call",
              content: `${block.name}: ${JSON.stringify(block.input)}`,
            };
          }
        }
      }
    } else if (message.type === "result") {
      yield {
        type: "result",
        content: extractMessageContent(message),
      };
    }
  }
}
