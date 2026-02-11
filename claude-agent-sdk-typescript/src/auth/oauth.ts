/**
 * OAuth authentication flow for MCP servers.
 * Implements a local callback server to handle OAuth redirects.
 * Supports PKCE (Proof Key for Code Exchange) for enhanced security.
 */

import http from "node:http";
import crypto from "node:crypto";
import { URL } from "node:url";

/**
 * Generate a cryptographically random code verifier for PKCE
 */
export function generateCodeVerifier(): string {
  // Generate 32 random bytes and encode as base64url
  const buffer = crypto.randomBytes(32);
  return buffer.toString("base64url");
}

/**
 * Generate the code challenge from the code verifier using SHA-256
 */
export function generateCodeChallenge(codeVerifier: string): string {
  const hash = crypto.createHash("sha256").update(codeVerifier).digest();
  return hash.toString("base64url");
}

interface CallbackData {
  authorizationCode: string | null;
  state: string | null;
  error: string | null;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
  refresh_token?: string;
  scope?: string;
}

/**
 * OAuth Callback Server - handles OAuth redirect callbacks
 */
export class OAuthCallbackServer {
  private server: http.Server | null = null;
  private port: number;
  private callbackData: CallbackData = {
    authorizationCode: null,
    state: null,
    error: null,
  };
  private resolveCallback: ((code: string) => void) | null = null;
  private rejectCallback: ((error: Error) => void) | null = null;

  constructor(port: number = 3030) {
    this.port = port;
  }

  get callbackUrl(): string {
    return `http://localhost:${this.port}/callback`;
  }

  /**
   * Start the callback server
   */
  start(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.server = http.createServer((req, res) => {
        this.handleRequest(req, res);
      });

      this.server.on("error", (err) => {
        console.error(`[OAuth] Server error: ${err.message}`);
        reject(err);
      });

      this.server.listen(this.port, () => {
        console.log(`[OAuth] Callback server started on http://localhost:${this.port}`);
        resolve();
      });
    });
  }

  /**
   * Stop the callback server
   */
  stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => {
          console.log("[OAuth] Callback server stopped");
          resolve();
        });
      } else {
        resolve();
      }
    });
  }

  /**
   * Handle incoming HTTP requests
   */
  private handleRequest(req: http.IncomingMessage, res: http.ServerResponse): void {
    const url = new URL(req.url || "/", `http://localhost:${this.port}`);
    console.log(`[OAuth] Received request: ${url.pathname}`);

    if (url.pathname === "/callback") {
      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state");
      const error = url.searchParams.get("error");

      if (error) {
        this.callbackData.error = error;
        this.sendErrorResponse(res, url.searchParams.get("error_description") || error);
        if (this.rejectCallback) {
          this.rejectCallback(new Error(`OAuth error: ${error}`));
        }
      } else if (code) {
        this.callbackData.authorizationCode = code;
        this.callbackData.state = state;
        this.sendSuccessResponse(res);
        if (this.resolveCallback) {
          this.resolveCallback(code);
        }
      } else {
        this.sendErrorResponse(res, "Invalid callback request");
      }
    } else {
      res.writeHead(404);
      res.end("Not Found");
    }
  }

  /**
   * Wait for the OAuth callback
   */
  waitForCallback(timeout: number = 300000): Promise<string> {
    return new Promise((resolve, reject) => {
      this.resolveCallback = resolve;
      this.rejectCallback = reject;

      setTimeout(() => {
        reject(new Error("OAuth callback timeout"));
      }, timeout);
    });
  }

  getState(): string | null {
    return this.callbackData.state;
  }

  private sendSuccessResponse(res: http.ServerResponse): void {
    const html = `
<!DOCTYPE html>
<html>
<head>
  <title>Authentication Successful</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
    }
    .container {
      text-align: center;
      padding: 40px;
      background: rgba(255,255,255,0.1);
      border-radius: 16px;
      backdrop-filter: blur(10px);
    }
    h1 { margin-bottom: 16px; }
    p { opacity: 0.9; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Authentication Successful</h1>
    <p>You can close this window and return to your terminal.</p>
    <script>setTimeout(() => window.close(), 2000);</script>
  </div>
</body>
</html>`;
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(html);
  }

  private sendErrorResponse(res: http.ServerResponse, message: string): void {
    const html = `
<!DOCTYPE html>
<html>
<head>
  <title>Authentication Failed</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
      background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
      color: white;
    }
    .container {
      text-align: center;
      padding: 40px;
      background: rgba(255,255,255,0.1);
      border-radius: 16px;
      backdrop-filter: blur(10px);
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Authentication Failed</h1>
    <p>${message}</p>
  </div>
</body>
</html>`;
    res.writeHead(400, { "Content-Type": "text/html" });
    res.end(html);
  }
}

/**
 * Exchange authorization code for tokens
 */
export async function exchangeCodeForTokens(
  tokenEndpoint: string,
  code: string,
  clientId: string,
  redirectUri: string,
  codeVerifier?: string
): Promise<TokenResponse> {
  const params = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    client_id: clientId,
    redirect_uri: redirectUri,
  });

  if (codeVerifier) {
    params.append("code_verifier", codeVerifier);
  }

  const response = await fetch(tokenEndpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params.toString(),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Token exchange failed: ${error}`);
  }

  return response.json();
}

/**
 * Open URL in the default browser
 */
export async function openBrowser(url: string): Promise<void> {
  const { exec } = await import("node:child_process");
  const { promisify } = await import("node:util");
  const execAsync = promisify(exec);

  const platform = process.platform;
  let command: string;

  if (platform === "darwin") {
    command = `open "${url}"`;
  } else if (platform === "win32") {
    command = `start "" "${url}"`;
  } else {
    command = `xdg-open "${url}"`;
  }

  try {
    await execAsync(command);
  } catch {
    console.log(`[OAuth] Could not open browser automatically.`);
    console.log(`[OAuth] Please visit: ${url}`);
  }
}
