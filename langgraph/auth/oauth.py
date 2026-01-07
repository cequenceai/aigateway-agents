"""OAuth authentication flow for MCP servers using MCP SDK."""

import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken


class InMemoryTokenStorage(TokenStorage):
    """Simple in-memory token storage implementation."""

    def __init__(self):
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._client_info = client_info


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    def __init__(self, request, client_address, server, callback_data):
        self.callback_data = callback_data
        super().__init__(request, client_address, server)

    def log_message(self, format: str, *args) -> None:
        """Suppress logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET request from OAuth redirect."""
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

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
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"🔐 Started OAuth callback server on http://localhost:{self.port}")

    def stop(self) -> None:
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for_callback(self, timeout: int = 300) -> str:
        """Wait for OAuth callback with timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.callback_data["authorization_code"]:
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                raise RuntimeError(f"OAuth error: {self.callback_data['error']}")
            time.sleep(0.1)
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

    async def callback_handler() -> tuple[str, str | None]:
        """Wait for OAuth callback and return auth code and state."""
        print("⏳ Waiting for authorization callback...")
        try:
            auth_code = callback_server.wait_for_callback(timeout=300)
            return auth_code, callback_server.get_state()
        finally:
            callback_server.stop()

    async def redirect_handler(authorization_url: str) -> None:
        """Open the authorization URL in the browser."""
        print(f"\n🔐 Opening browser for authentication...")
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
