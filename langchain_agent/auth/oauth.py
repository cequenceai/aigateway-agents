"""OAuth authentication flow for MCP servers using MCP SDK."""

import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken


class InMemoryTokenStorage(TokenStorage):
    """Token storage that persists to disk."""

    def __init__(self, storage_dir: str | None = None):
        import os
        from pathlib import Path
        
        if storage_dir is None:
            # Default to .tokens directory in user's home
            self.storage_dir = Path.home() / ".mcp_agent_tokens"
        else:
            self.storage_dir = Path(storage_dir)
        
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.tokens_file = self.storage_dir / "oauth_tokens.json"
        self.client_info_file = self.storage_dir / "oauth_client_info.json"
        
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None
        
        # Load existing tokens from disk
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load tokens and client info from disk."""
        import json
        try:
            if self.tokens_file.exists():
                with open(self.tokens_file, 'r') as f:
                    data = json.load(f)
                    self._tokens = OAuthToken.model_validate(data)
        except Exception:
            pass  # If loading fails, tokens remain None
        
        try:
            if self.client_info_file.exists():
                with open(self.client_info_file, 'r') as f:
                    data = json.load(f)
                    self._client_info = OAuthClientInformationFull.model_validate(data)
        except Exception:
            pass  # If loading fails, client_info remains None

    def _save_to_disk(self) -> None:
        """Save tokens and client info to disk."""
        import json
        try:
            if self._tokens:
                with open(self.tokens_file, 'w') as f:
                    json.dump(self._tokens.model_dump(), f, indent=2)
        except Exception:
            pass  # If saving fails, continue
        
        try:
            if self._client_info:
                with open(self.client_info_file, 'w') as f:
                    json.dump(self._client_info.model_dump(), f, indent=2)
        except Exception:
            pass  # If saving fails, continue

    async def get_tokens(self) -> OAuthToken | None:
        if self._tokens is None:
            self._load_from_disk()
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens
        self._save_to_disk()

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        if self._client_info is None:
            self._load_from_disk()
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._client_info = client_info
        self._save_to_disk()


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    def __init__(self, request, client_address, server, callback_data):
        self.callback_data = callback_data
        super().__init__(request, client_address, server)

    def log_message(self, format: str, *args) -> None:
        """Suppress logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET request from OAuth redirect - accepts any path."""
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        
        # Debug: print what we received
        print(f"🔍 Received GET request: path={self.path}")
        print(f"🔍 Query params: {list(query_params.keys())}")

        if "code" in query_params:
            code = query_params["code"][0]
            state = query_params.get("state", [None])[0]
            print(f"✓ Received authorization code! (length: {len(code)})")
            self.callback_data["authorization_code"] = code
            self.callback_data["state"] = state
            self._send_success_response()
        elif "error" in query_params:
            error = query_params.get("error", ["unknown"])[0]
            error_desc = query_params.get("error_description", [""])[0]
            print(f"✗ OAuth error: {error} - {error_desc}")
            self.callback_data["error"] = error
            self._send_error_response(error_desc)
        else:
            # No code or error - might be a different request (like favicon)
            print(f"⚠ Request without code/error: {self.path}")
            # Send a simple response instead of error for non-OAuth requests
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>OAuth callback server is running. Waiting for authorization...</body></html>")

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


def find_available_port(start_port: int = 3030, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    import socket
    
    for i in range(max_attempts):
        port = start_port + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue
    
    raise RuntimeError(f"Could not find an available port starting from {start_port}")


class CallbackServer:
    """Server to handle OAuth callbacks."""

    def __init__(self, port: int = 3030, auto_find_port: bool = True):
        """
        Initialize callback server.
        
        Args:
            port: Preferred port number
            auto_find_port: If True, automatically find another port if preferred is in use
        """
        self.preferred_port = port
        self.port = port
        self.auto_find_port = auto_find_port
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
        
        # Try to start on preferred port, or find available port if auto_find_port is True
        if self.auto_find_port:
            try:
                self.server = HTTPServer(("localhost", self.port), handler_class)
            except OSError:
                # Port is in use, find another one
                self.port = find_available_port(self.preferred_port)
                print(f"⚠ Port {self.preferred_port} is in use, using port {self.port} instead")
                self.server = HTTPServer(("localhost", self.port), handler_class)
        else:
            self.server = HTTPServer(("localhost", self.port), handler_class)
        
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"🔐 Started OAuth callback server on http://localhost:{self.port}")
        print(f"   Callback URL: http://localhost:{self.port}/callback")

    def stop(self) -> None:
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for_callback(self, timeout: int = 60) -> str:
        """Wait for OAuth callback with timeout (default 1 minute)."""
        start_time = time.time()
        last_status_time = start_time
        status_interval = 10  # Print status every 10 seconds
        
        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time
            
            # Print status every 10 seconds
            if time.time() - last_status_time >= status_interval:
                remaining = int(timeout - elapsed)
                print(f"⏳ Still waiting... ({remaining}s remaining)")
                last_status_time = time.time()
            
            if self.callback_data["authorization_code"]:
                elapsed_total = int(time.time() - start_time)
                print(f"✓ Authorization callback received! ({elapsed_total}s)")
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                raise RuntimeError(f"OAuth error: {self.callback_data['error']}")
            
            time.sleep(0.1)
        
        elapsed_total = int(time.time() - start_time)
        raise TimeoutError(f"Timeout waiting for OAuth callback after {elapsed_total}s. Please check if the browser opened and you completed the authorization.")

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
    # Create storage instance (will load existing tokens from disk)
    storage = InMemoryTokenStorage()
    
    # Check if we already have tokens (synchronously, since tokens are loaded from disk in __init__)
    # Note: We check _tokens directly instead of calling async get_tokens() to avoid event loop issues
    try:
        # Tokens are already loaded from disk in __init__, so we can check directly
        if storage._tokens is not None:
            print("✓ Found existing OAuth tokens, skipping authentication")
            # Still create provider but it should use existing tokens
    except Exception:
        pass  # If check fails, proceed with OAuth flow

    async def callback_handler() -> tuple[str, str | None]:
        """Wait for OAuth callback and return auth code and state."""
        print("⏳ Waiting for authorization callback...")
        print("   (Timeout: 60 seconds)")
        try:
            auth_code = callback_server.wait_for_callback(timeout=60)  # 1 minute timeout
            return auth_code, callback_server.get_state()
        except TimeoutError as e:
            print(f"\n❌ {e}")
            print("\nTroubleshooting:")
            print("  1. Check if the browser opened")
            print("  2. Verify you completed the authorization")
            print("  3. Check if port 3030 is accessible")
            print("  4. Try manually visiting the authorization URL shown above")
            raise
        finally:
            callback_server.stop()

    async def redirect_handler(authorization_url: str) -> None:
        """Open the authorization URL in the browser."""
        print(f"\n🔐 Opening browser for authentication...")
        print(f"   If the browser doesn't open, visit:\n   {authorization_url}\n")
        try:
            # Try Chrome first on macOS
            import subprocess
            import platform
            if platform.system() == "Darwin":  # macOS
                try:
                    # Try to open with Chrome
                    subprocess.run(["open", "-a", "Google Chrome", authorization_url], check=True)
                    print("   ✓ Chrome browser opened successfully")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Fall back to default browser
                    webbrowser.open(authorization_url)
                    print("   ✓ Browser opened successfully (default)")
            else:
                # On other systems, try Chrome first, then default
                try:
                    chrome = webbrowser.get('chrome')
                    chrome.open(authorization_url)
                    print("   ✓ Chrome browser opened successfully")
                except webbrowser.Error:
                    webbrowser.open(authorization_url)
                    print("   ✓ Browser opened successfully (default)")
        except Exception as e:
            print(f"   ⚠ Could not open browser automatically: {e}")
            print(f"   Please manually visit: {authorization_url}")

    client_metadata = OAuthClientMetadata.model_validate({
        "client_name": "MCP Agent CLI",
        "redirect_uris": [callback_server.callback_url],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    })

    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )
