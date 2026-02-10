"""OAuth authentication flow for MCP servers using MCP SDK."""

import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken


# Global start time for timing (set when oauth provider is created)
_oauth_start_time: float | None = None


def _oauth_elapsed() -> str:
    """Get elapsed time since OAuth started."""
    if _oauth_start_time is None:
        return "?.???s"
    return f"{time.time() - _oauth_start_time:.3f}s"


class InMemoryTokenStorage(TokenStorage):
    """Simple in-memory token storage implementation."""

    def __init__(self):
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None
        self._get_tokens_count = 0

    async def get_tokens(self) -> OAuthToken | None:
        self._get_tokens_count += 1
        has_tokens = self._tokens is not None
        # Only log the first few calls to avoid spam
        if self._get_tokens_count <= 3 or has_tokens:
            print(f"   [TokenStorage T+{_oauth_elapsed()}] get_tokens() called (#{self._get_tokens_count}), has_tokens={has_tokens}")
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        print(f"   [TokenStorage T+{_oauth_elapsed()}] ✓ set_tokens() called - tokens received!")
        # Print token details for debugging (without exposing full token)
        if hasattr(tokens, 'access_token') and tokens.access_token:
            print(f"   [TokenStorage T+{_oauth_elapsed()}]   access_token: {tokens.access_token[:30]}...")
        if hasattr(tokens, 'refresh_token') and tokens.refresh_token:
            print(f"   [TokenStorage T+{_oauth_elapsed()}]   refresh_token: {tokens.refresh_token[:30]}...")
        else:
            print(f"   [TokenStorage T+{_oauth_elapsed()}]   refresh_token: None")
        if hasattr(tokens, 'token_type'):
            print(f"   [TokenStorage T+{_oauth_elapsed()}]   token_type: {tokens.token_type}")
        if hasattr(tokens, 'expires_in'):
            print(f"   [TokenStorage T+{_oauth_elapsed()}]   expires_in: {tokens.expires_in}")
        if hasattr(tokens, 'scope'):
            print(f"   [TokenStorage T+{_oauth_elapsed()}]   scope: {tokens.scope}")
        # Print all token fields for debugging
        print(f"   [TokenStorage T+{_oauth_elapsed()}]   All fields: {list(tokens.__dict__.keys()) if hasattr(tokens, '__dict__') else dir(tokens)}")
        self._tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        print(f"   [TokenStorage T+{_oauth_elapsed()}] get_client_info() called, has_info={self._client_info is not None}")
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        print(f"   [TokenStorage T+{_oauth_elapsed()}] ✓ set_client_info() called - client registered!")
        self._client_info = client_info


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    def __init__(self, request, client_address, server, callback_data):
        self.callback_data = callback_data
        super().__init__(request, client_address, server)

    def log_message(self, format: str, *args) -> None:
        """Log all requests for debugging."""
        print(f"   [Callback Server] {format % args}")

    def do_GET(self) -> None:
        """Handle GET request from OAuth redirect."""
        print(f"   [Callback Server] Received GET request: {self.path}")
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        print(f"   [Callback Server] Path: {parsed.path}")
        print(f"   [Callback Server] Query params: {list(query_params.keys())}")

        if "code" in query_params:
            self.callback_data["authorization_code"] = query_params["code"][0]
            self.callback_data["state"] = query_params.get("state", [None])[0]
            self._send_success_response()
        elif "error" in query_params:
            self.callback_data["error"] = query_params.get("error", ["unknown"])[0]
            self._send_error_response(query_params.get("error_description", [""])[0])
        else:
            self._send_error_response("Invalid callback request")

    def _send_success_response(self) -> None:
        """Send success HTML response."""
        html = b"""
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
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html)

    def _send_error_response(self, message: str = "Authentication failed") -> None:
        """Send error HTML response."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
                    color: white;
                }}
                .container {{
                    text-align: center;
                    padding: 40px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 16px;
                    backdrop-filter: blur(10px);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Authentication Failed</h1>
                <p>{message}</p>
            </div>
        </body>
        </html>
        """
        self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())


class CallbackServer:
    """Server to handle OAuth callbacks."""

    def __init__(self, port: int = 3030):
        self.port = port
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._stopped = threading.Event()
        self._running = False
        self.callback_data = {
            "authorization_code": None,
            "state": None,
            "error": None,
        }

    def _create_handler_with_data(self):
        """Create a handler class with access to callback data."""
        callback_data = self.callback_data

        class DataCallbackHandler(CallbackHandler):
            def __init__(self, request, client_address, server):
                super().__init__(request, client_address, server, callback_data)

        return DataCallbackHandler

    def start(self) -> None:
        """Start the callback server in a background thread."""
        handler_class = self._create_handler_with_data()
        self.server = HTTPServer(("localhost", self.port), handler_class)
        self._stopped.clear()
        self._running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        print(f"🔐 Started OAuth callback server on http://localhost:{self.port}")

    def _serve(self) -> None:
        """Internal method to run serve_forever and signal when done."""
        try:
            if self.server:
                self.server.serve_forever()
        finally:
            self._running = False
            self._stopped.set()

    def stop(self, timeout: float = 2.0) -> bool:
        """
        Stop the callback server and wait for it to fully shut down.
        
        Args:
            timeout: Maximum time to wait for shutdown (default: 2s)
            
        Returns:
            True if server stopped cleanly, False if timeout occurred
        """
        if not self._running and self._stopped.is_set():
            return True  # Already stopped
            
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        # Wait for the server thread to finish
        if self.thread and self.thread.is_alive():
            stopped = self._stopped.wait(timeout=timeout)
            if not stopped:
                print(f"   [OAuth] ⚠️  Callback server didn't stop within {timeout}s")
                return False
        
        return True
    
    @property
    def is_running(self) -> bool:
        """Check if the callback server is still running."""
        return self._running

    def wait_for_callback_sync(self, timeout: int = 300) -> str:
        """Wait for OAuth callback with timeout (synchronous, blocks event loop)."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.callback_data["authorization_code"]:
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                raise RuntimeError(f"OAuth error: {self.callback_data['error']}")
            time.sleep(0.1)
        raise TimeoutError("Timeout waiting for OAuth callback")
    
    async def wait_for_callback(self, timeout: int = 300) -> str:
        """Wait for OAuth callback with timeout (async, doesn't block event loop)."""
        import asyncio
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.callback_data["authorization_code"]:
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                raise RuntimeError(f"OAuth error: {self.callback_data['error']}")
            await asyncio.sleep(0.1)  # Non-blocking sleep
        raise TimeoutError("Timeout waiting for OAuth callback")

    def get_state(self) -> str | None:
        """Get the received state parameter."""
        return self.callback_data["state"]

    @property
    def callback_url(self) -> str:
        """Get the callback URL."""
        return f"http://localhost:{self.port}/callback"


def create_oauth_provider(
    server_url: str,
    callback_server: CallbackServer,
) -> OAuthClientProvider:
    """
    Create an OAuthClientProvider for MCP authentication.

    Args:
        server_url: The MCP server URL (without /mcp suffix)
        callback_server: The callback server instance

    Returns:
        OAuthClientProvider configured for the server
    """
    global _oauth_start_time
    _oauth_start_time = time.time()

    async def callback_handler() -> tuple[str, str | None]:
        """Wait for OAuth callback and return auth code and state."""
        print(f"⏳ [OAuth T+{_oauth_elapsed()}] Waiting for authorization callback (async, non-blocking)...")
        wait_start = time.time()
        try:
            # Use async version to not block the event loop
            auth_code = await callback_server.wait_for_callback(timeout=300)
            wait_elapsed = time.time() - wait_start
            state = callback_server.get_state()
            print(f"   [OAuth T+{_oauth_elapsed()}] ✓ Received authorization code after {wait_elapsed:.2f}s: {auth_code[:20]}...")
            print(f"   [OAuth T+{_oauth_elapsed()}] ✓ State: {state[:20] if state else 'None'}...")
            print(f"   [OAuth T+{_oauth_elapsed()}] Returning code to OAuth provider for token exchange...")
            return auth_code, state
        except Exception as e:
            print(f"   [OAuth T+{_oauth_elapsed()}] ✗ Error in callback_handler: {type(e).__name__}: {e}")
            raise
        finally:
            print(f"   [OAuth T+{_oauth_elapsed()}] Stopping callback server...")
            stop_start = time.time()
            stopped_cleanly = callback_server.stop(timeout=2.0)
            stop_elapsed = time.time() - stop_start
            if stopped_cleanly:
                print(f"   [OAuth T+{_oauth_elapsed()}] ✓ Callback server stopped cleanly in {stop_elapsed:.3f}s")
            else:
                print(f"   [OAuth T+{_oauth_elapsed()}] ⚠️  Callback server stop timed out after {stop_elapsed:.3f}s")

    async def redirect_handler(authorization_url: str) -> None:
        """Open the authorization URL in the browser."""
        print(f"\n🔐 [OAuth T+{_oauth_elapsed()}] Opening browser for authentication...")
        print(f"   If the browser doesn't open, visit:\n   {authorization_url}\n")
        webbrowser.open(authorization_url)

    client_metadata = OAuthClientMetadata.model_validate({
        "client_name": "MCP Agent CLI",
        "redirect_uris": [callback_server.callback_url],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    })

    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=InMemoryTokenStorage(),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )
