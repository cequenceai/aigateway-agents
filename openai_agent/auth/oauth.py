"""OAuth authentication flow for MCP servers using MCP SDK."""

import logging
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

logger = logging.getLogger(__name__)


class InMemoryTokenStorage(TokenStorage):
    """Token storage that persists to disk."""

    def __init__(self, storage_dir: str | None = None, reset_tokens: bool = False):
        import os
        from pathlib import Path
        
        if storage_dir is None:
            self.storage_dir = Path.home() / ".mcp_agent_tokens"
        else:
            self.storage_dir = Path(storage_dir)
        
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.tokens_file = self.storage_dir / "oauth_tokens.json"
        self.client_info_file = self.storage_dir / "oauth_client_info.json"
        
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None
        
        if not reset_tokens:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load tokens and client info from disk."""
        import json
        try:
            if self.tokens_file.exists():
                with open(self.tokens_file, 'r') as f:
                    data = json.load(f)
                    self._tokens = OAuthToken.model_validate(data)
                    logger.info("✓ Loaded tokens from disk")
        except Exception as e:
            logger.debug(f"Could not load tokens from disk: {e}")
        
        try:
            if self.client_info_file.exists():
                with open(self.client_info_file, 'r') as f:
                    data = json.load(f)
                    self._client_info = OAuthClientInformationFull.model_validate(data)
                    logger.info("✓ Loaded client info from disk")
        except Exception as e:
            logger.debug(f"Could not load client info from disk: {e}")

    def _save_to_disk(self) -> None:
        """Save tokens and client info to disk."""
        import json
        try:
            if self._tokens:
                with open(self.tokens_file, 'w') as f:
                    json.dump(self._tokens.model_dump(), f, indent=2)
        except Exception:
            pass
        
        try:
            if self._client_info:
                with open(self.client_info_file, 'w') as f:
                    json.dump(self._client_info.model_dump(), f, indent=2)
        except Exception:
            pass

    async def get_tokens(self) -> OAuthToken | None:
        if self._tokens is None:
            self._load_from_disk()
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens
        logger.info("✓ Tokens saved")
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
        """Handle GET request from OAuth redirect."""
        # Log all incoming requests for debugging
        logger.info(f"📥 Received GET request: {self.path}")
        print(f"📥 Received GET request: {self.path}")
        
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')  # Remove trailing slash
        
        # Handle /callback path (with or without trailing slash)
        if path == '/callback' or path == '':
            query_params = parse_qs(parsed.query)
            logger.info(f"📋 Query params: {list(query_params.keys())}")
            
            if "code" in query_params:
                code = query_params["code"][0]
                state = query_params.get("state", [None])[0]
                logger.info(f"✓ Received authorization code (length: {len(code)})")
                print(f"✓ Received authorization code (length: {len(code)})")
                self.callback_data["authorization_code"] = code
                self.callback_data["state"] = state
                self._send_success_response()
            elif "error" in query_params:
                error = query_params.get("error", ["unknown"])[0]
                error_desc = query_params.get("error_description", [""])[0]
                logger.error(f"✗ OAuth error: {error} - {error_desc}")
                print(f"✗ OAuth error: {error} - {error_desc}")
                self.callback_data["error"] = error
                self._send_error_response(error_desc)
            else:
                # No code or error - might be a browser preflight or other request
                logger.warning(f"⚠ GET request to /callback without code or error parameter")
                print(f"⚠ GET request to /callback without code or error parameter")
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body>OAuth callback server is running. Waiting for authorization...</body></html>")
        else:
            # Not a callback path - respond with info
            logger.info(f"ℹ️  GET request to non-callback path: {path}")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>OAuth callback server is running. Use /callback for OAuth redirects.</body></html>")

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
        
        if self.auto_find_port:
            try:
                self.server = HTTPServer(("localhost", self.port), handler_class)
                logger.info(f"✓ Callback server started on port {self.port}")
                print(f"✓ Callback server started on port {self.port}")
            except OSError:
                self.port = find_available_port(self.preferred_port)
                logger.warning(f"⚠ Port {self.preferred_port} in use, using port {self.port}")
                print(f"⚠ Port {self.preferred_port} in use, using port {self.port}")
                self.server = HTTPServer(("localhost", self.port), handler_class)
                logger.info(f"✓ Callback server started on port {self.port}")
                print(f"✓ Callback server started on port {self.port}")
        else:
            self.server = HTTPServer(("localhost", self.port), handler_class)
            logger.info(f"✓ Callback server started on port {self.port}")
            print(f"✓ Callback server started on port {self.port}")
        
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"✓ Callback server thread started")
        print(f"✓ Callback server listening on: {self.callback_url}")

    def stop(self) -> None:
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for_callback(self, timeout: int = 180) -> str:
        """Wait for OAuth callback with timeout."""
        logger.info(f"⏳ Waiting for OAuth callback (timeout: {timeout}s)")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.callback_data["authorization_code"]:
                elapsed = int(time.time() - start_time)
                logger.info(f"✓ Authorization callback received after {elapsed}s")
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                error_msg = f"OAuth error: {self.callback_data['error']}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            time.sleep(0.1)
        
        elapsed = int(time.time() - start_time)
        timeout_msg = f"Timeout waiting for OAuth callback after {elapsed}s"
        logger.error(timeout_msg)
        raise TimeoutError(timeout_msg)

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
    reset_tokens: bool = False,
) -> OAuthClientProvider:
    """
    Create an OAuthClientProvider for MCP authentication.

    Args:
        server_url: The MCP server URL (without /mcp suffix)
        callback_server: The callback server instance
        reset_tokens: If True, don't load saved tokens

    Returns:
        OAuthClientProvider configured for the server
    """
    logger.info("Creating OAuth Provider")
    logger.info(f"Server URL: {server_url}")
    logger.info(f"Callback URL: {callback_server.callback_url}")
    
    storage = InMemoryTokenStorage(reset_tokens=reset_tokens)
    
    async def callback_handler() -> tuple[str, str | None]:
        """Wait for OAuth callback and return auth code and state."""
        logger.info("Callback handler invoked - waiting for authorization code")
        print("\n⏳ Waiting for authorization callback...")
        print("   Please complete the OAuth flow in your browser.\n")
        try:
            auth_code = callback_server.wait_for_callback(timeout=180)
            state = callback_server.get_state()
            return auth_code, state
        except TimeoutError as e:
            logger.error(f"❌ Timeout waiting for callback: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Exception in callback handler: {e}")
            raise

    async def redirect_handler(authorization_url: str) -> None:
        """Open the authorization URL in the browser."""
        logger.info("="*70)
        logger.info("🔐 Opening Browser for OAuth")
        logger.info("="*70)
        logger.info(f"Authorization URL: {authorization_url}")
        logger.info("="*70)
        
        print("\n" + "="*80)
        print("🔐 OAUTH AUTHENTICATION REQUIRED")
        print("="*80)
        print("\n⚠️  Please complete OAuth authentication in your browser.")
        print("\n📋 AUTHORIZATION URL:")
        print("-" * 80)
        print(authorization_url)
        print("-" * 80)
        print("\n⏳ Attempting to open browser automatically...\n")
        
        browser_opened = False
        try:
            # Try Chrome first on macOS
            import subprocess
            import platform
            if platform.system() == "Darwin":  # macOS
                try:
                    # Try to open with Chrome
                    subprocess.run(["open", "-a", "Google Chrome", authorization_url], check=True)
                    browser_opened = True
                    logger.info("✓ Chrome browser opened successfully")
                    print("   ✓ Chrome browser opened successfully")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Fall back to default browser
                    result = webbrowser.open(authorization_url)
                    if result:
                        browser_opened = True
                        logger.info("✓ Browser opened successfully (default)")
                        print("   ✓ Browser opened successfully (default)")
            else:
                # On other systems, try Chrome first, then default
                try:
                    chrome = webbrowser.get('chrome')
                    chrome.open(authorization_url)
                    browser_opened = True
                    logger.info("✓ Chrome browser opened successfully")
                    print("   ✓ Chrome browser opened successfully")
                except webbrowser.Error:
                    result = webbrowser.open(authorization_url)
                    if result:
                        browser_opened = True
                        logger.info("✓ Browser opened successfully (default)")
                        print("   ✓ Browser opened successfully (default)")
        except Exception as e:
            logger.warning(f"Could not open browser: {e}")
        
        if not browser_opened:
            print("\n⚠️  BROWSER DID NOT OPEN AUTOMATICALLY")
            print("Please manually open your browser and visit the URL above.\n")
        else:
            print("✓ Browser should be opening now. Please complete the OAuth flow.\n")
        
        print("📋 Authorization URL (for manual copy/paste):")
        print(f"   {authorization_url}\n")

    client_metadata_dict = {
        "client_name": "OpenAI Agent",
        "redirect_uris": [callback_server.callback_url],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    
    client_metadata = OAuthClientMetadata.model_validate(client_metadata_dict)
    
    provider = OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )
    
    logger.info("✓ OAuth provider created")
    
    return provider
