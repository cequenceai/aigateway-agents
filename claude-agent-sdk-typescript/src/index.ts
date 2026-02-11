#!/usr/bin/env node
/**
 * MCP Agent CLI - Interactive terminal agent connected to MCP servers.
 * Uses the Claude Agent SDK for TypeScript.
 *
 * Usage:
 *   npx tsx src/index.ts --mcp-url http://localhost:8000/mcp
 *   npx tsx src/index.ts --mcp-url http://localhost:8000/mcp --auth-token "your-token"
 */

import readline from "node:readline";
import { parseArgs } from "node:util";
import { OAuthCallbackServer, openBrowser, exchangeCodeForTokens, generateCodeVerifier, generateCodeChallenge } from "./auth/oauth.js";
import { runQuery, type AgentConfig } from "./agent/mcp-agent.js";

// ANSI color codes for terminal output
const colors = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  blue: "\x1b[34m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
};

function printBanner(): void {
  console.log();
  console.log(`${colors.bold}${colors.blue}╔══════════════════════════════════════════════════════════╗${colors.reset}`);
  console.log(`${colors.bold}${colors.blue}║  MCP Agent - Claude Agent SDK (TypeScript)               ║${colors.reset}`);
  console.log(`${colors.bold}${colors.blue}╚══════════════════════════════════════════════════════════╝${colors.reset}`);
  console.log();
}

function printHelp(): void {
  console.log(`
${colors.bold}Usage:${colors.reset}
  npx tsx src/index.ts --mcp-url <url> [options]

${colors.bold}Options:${colors.reset}
  --mcp-url <url>      MCP server URL (required)
  --auth-token <token> Authorization token (Bearer token)
  --no-oauth           Disable automatic OAuth flow
  --model <model>      Claude model to use (default: claude-sonnet-4-20250514)
  --help               Show this help message

${colors.bold}Environment Variables:${colors.reset}
  ANTHROPIC_API_KEY    API key for Anthropic (required)

${colors.bold}Examples:${colors.reset}
  # Basic usage (will auto-handle OAuth if server requires it)
  npx tsx src/index.ts --mcp-url http://localhost:8000/mcp

  # With static auth token
  npx tsx src/index.ts --mcp-url http://localhost:8000/mcp --auth-token "Bearer my-token"

${colors.bold}Commands (in chat):${colors.reset}
  /quit, /exit, /q     Exit the chat
  /clear               Clear conversation history
  /help                Show available commands
`);
}

interface ParsedArgs {
  mcpUrl?: string;
  authToken?: string;
  noOauth?: boolean;
  model?: string;
  help?: boolean;
}

function parseCliArgs(): ParsedArgs {
  try {
    const { values } = parseArgs({
      options: {
        "mcp-url": { type: "string" },
        "auth-token": { type: "string" },
        "no-oauth": { type: "boolean", default: false },
        model: { type: "string" },
        help: { type: "boolean", default: false },
      },
      allowPositionals: true,
    });

    return {
      mcpUrl: values["mcp-url"],
      authToken: values["auth-token"],
      noOauth: values["no-oauth"],
      model: values.model,
      help: values.help,
    };
  } catch {
    return { help: true };
  }
}

/**
 * Perform OAuth flow if needed
 */
async function performOAuthFlow(baseUrl: string): Promise<string | null> {
  console.log(`${colors.dim}[OAuth] Starting OAuth flow...${colors.reset}`);

  const callbackServer = new OAuthCallbackServer(3030);

  try {
    await callbackServer.start();

    // Discover OAuth endpoints from the server
    const wellKnownUrl = `${baseUrl}/.well-known/oauth-authorization-server`;
    console.log(`${colors.dim}[OAuth] Fetching OAuth metadata from ${wellKnownUrl}${colors.reset}`);

    const metadataResponse = await fetch(wellKnownUrl);
    if (!metadataResponse.ok) {
      console.log(`${colors.yellow}[OAuth] No OAuth metadata found, server may not require auth${colors.reset}`);
      await callbackServer.stop();
      return null;
    }

    const metadata = await metadataResponse.json() as {
      authorization_endpoint: string;
      token_endpoint: string;
      registration_endpoint?: string;
    };

    // Dynamic client registration if supported
    let clientId = "mcp-agent-cli";
    if (metadata.registration_endpoint) {
      console.log(`${colors.dim}[OAuth] Registering client...${colors.reset}`);
      const regResponse = await fetch(metadata.registration_endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_name: "MCP Agent CLI (TypeScript)",
          redirect_uris: [callbackServer.callbackUrl],
          grant_types: ["authorization_code", "refresh_token"],
          response_types: ["code"],
        }),
      });

      if (regResponse.ok) {
        const regData = await regResponse.json() as { client_id: string };
        clientId = regData.client_id;
        console.log(`${colors.dim}[OAuth] Registered client: ${clientId}${colors.reset}`);
      }
    }

    // Generate PKCE code verifier and challenge
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = generateCodeChallenge(codeVerifier);
    console.log(`${colors.dim}[OAuth] Generated PKCE code challenge${colors.reset}`);

    // Build authorization URL with PKCE
    const state = Math.random().toString(36).substring(2, 15);
    const authUrl = new URL(metadata.authorization_endpoint);
    authUrl.searchParams.set("client_id", clientId);
    authUrl.searchParams.set("redirect_uri", callbackServer.callbackUrl);
    authUrl.searchParams.set("response_type", "code");
    authUrl.searchParams.set("state", state);
    authUrl.searchParams.set("code_challenge", codeChallenge);
    authUrl.searchParams.set("code_challenge_method", "S256");

    console.log(`\n${colors.bold}[OAuth] Opening browser for authentication...${colors.reset}`);
    console.log(`${colors.dim}If the browser doesn't open, visit:${colors.reset}`);
    console.log(`${colors.cyan}${authUrl.toString()}${colors.reset}\n`);

    await openBrowser(authUrl.toString());

    // Wait for callback
    console.log(`${colors.dim}[OAuth] Waiting for authorization callback...${colors.reset}`);
    const code = await callbackServer.waitForCallback(300000);
    console.log(`${colors.green}[OAuth] Received authorization code${colors.reset}`);

    // Exchange code for tokens with PKCE code verifier
    console.log(`${colors.dim}[OAuth] Exchanging code for tokens...${colors.reset}`);
    const tokens = await exchangeCodeForTokens(
      metadata.token_endpoint,
      code,
      clientId,
      callbackServer.callbackUrl,
      codeVerifier  // Pass the code verifier for PKCE
    );

    console.log(`${colors.green}[OAuth] Authentication successful!${colors.reset}`);
    return tokens.access_token;
  } catch (error) {
    if (error instanceof Error) {
      console.log(`${colors.yellow}[OAuth] OAuth flow failed: ${error.message}${colors.reset}`);
    }
    return null;
  } finally {
    await callbackServer.stop();
  }
}

/**
 * Run the interactive chat loop
 */
async function chatLoop(config: AgentConfig): Promise<void> {
  const conversationHistory: Array<{ role: string; content: string }> = [];

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log(`${colors.dim}Type your message and press Enter. Use /quit to exit.${colors.reset}\n`);

  const prompt = (): void => {
    rl.question(`${colors.bold}${colors.green}You:${colors.reset} `, async (input) => {
      const trimmedInput = input.trim();

      if (!trimmedInput) {
        prompt();
        return;
      }

      // Handle special commands
      if (["/quit", "/exit", "/q"].includes(trimmedInput.toLowerCase())) {
        console.log(`\n${colors.dim}Goodbye!${colors.reset}`);
        rl.close();
        return;
      }

      if (trimmedInput.toLowerCase() === "/clear") {
        conversationHistory.length = 0;
        console.clear();
        printBanner();
        console.log(`${colors.dim}Conversation cleared.${colors.reset}\n`);
        prompt();
        return;
      }

      if (trimmedInput.toLowerCase() === "/help") {
        console.log(`
${colors.bold}Commands:${colors.reset}
  /quit, /exit, /q  - Exit the chat
  /clear            - Clear conversation history
  /help             - Show this help message
`);
        prompt();
        return;
      }

      // Add user message to history
      conversationHistory.push({ role: "user", content: trimmedInput });

      console.log(`\n${colors.bold}${colors.blue}Assistant:${colors.reset}`);

      try {
        // Show thinking indicator
        process.stdout.write(`${colors.dim}Thinking...${colors.reset}`);

        const response = await runQuery(trimmedInput, config, conversationHistory);

        // Clear thinking indicator
        process.stdout.write("\r" + " ".repeat(20) + "\r");

        console.log(response);

        // Add assistant response to history
        conversationHistory.push({ role: "assistant", content: response });
      } catch (error) {
        // Clear thinking indicator
        process.stdout.write("\r" + " ".repeat(20) + "\r");

        if (error instanceof Error) {
          console.log(`${colors.red}Error: ${error.message}${colors.reset}`);
        }
      }

      console.log();
      prompt();
    });
  };

  prompt();

  // Handle Ctrl+C
  rl.on("SIGINT", () => {
    console.log(`\n\n${colors.dim}Goodbye!${colors.reset}`);
    rl.close();
    process.exit(0);
  });
}

/**
 * Main entry point
 */
async function main(): Promise<void> {
  const args = parseCliArgs();

  if (args.help) {
    printHelp();
    process.exit(0);
  }

  if (!args.mcpUrl) {
    console.error(`${colors.red}Error: --mcp-url is required${colors.reset}`);
    printHelp();
    process.exit(1);
  }

  // Check for API key
  if (!process.env.ANTHROPIC_API_KEY) {
    console.error(`${colors.red}Error: ANTHROPIC_API_KEY environment variable is required${colors.reset}`);
    process.exit(1);
  }

  printBanner();

  console.log(`${colors.dim}Connecting to MCP server: ${args.mcpUrl}${colors.reset}`);

  // Determine auth token
  let authToken = args.authToken;

  // If no auth token and OAuth not disabled, try OAuth flow
  if (!authToken && !args.noOauth) {
    const baseUrl = args.mcpUrl.replace(/\/mcp$/, "");
    authToken = await performOAuthFlow(baseUrl) || undefined;
  }

  const config: AgentConfig = {
    mcpUrl: args.mcpUrl,
    authToken,
    model: args.model,
  };

  console.log(`${colors.dim}Using model: ${config.model || "claude-sonnet-4-20250514"}${colors.reset}`);
  if (authToken) {
    console.log(`${colors.dim}Authentication: ${authToken.startsWith("Bearer ") ? "Bearer token" : "Token"} configured${colors.reset}`);
  }
  console.log();

  await chatLoop(config);
}

main().catch((error) => {
  console.error(`${colors.red}Fatal error: ${error.message}${colors.reset}`);
  process.exit(1);
});
