"""OAuth provider interface for Lynx Codex authentication."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable
import os

logger = logging.getLogger(__name__)

# Try to import keyring, but allow fallback if no backend available
try:
    import keyring
    _KEYRING_AVAILABLE = True
    _KEYRING_ERROR = None
    try:
        # Test if keyring has a working backend
        keyring.get_password("lynx_codex_test", "test")
    except Exception as e:
        _KEYRING_AVAILABLE = False
        _KEYRING_ERROR = str(e)
        logger.warning(f"Keyring backend not available: {_KEYRING_ERROR}. OAuth tokens will not be persisted.")
except ImportError:
    keyring = None
    _KEYRING_AVAILABLE = False
    _KEYRING_ERROR = "keyring package not installed"


@dataclass
class TokenPair:
    """OAuth token pair returned after successful authentication."""
    access_token: str
    refresh_token: str
    expires_in: int  # seconds
    token_type: str = "Bearer"


@dataclass
class AuthCode:
    """Authorization code from OAuth callback."""
    code: str
    state: Optional[str] = None


class TokenStorage(ABC):
    """Abstract token storage interface. Implement to add new storage backends."""

    @abstractmethod
    def save(self, provider_name: str, tokens: TokenPair) -> None:
        """Persist tokens to storage."""
        pass

    @abstractmethod
    def load(self, provider_name: str) -> Optional[TokenPair]:
        """Load tokens from storage, or None if not found/expired."""
        pass

    @abstractmethod
    def delete(self, provider_name: str) -> None:
        """Remove tokens from storage (logout)."""
        pass

    @abstractmethod
    def is_expired(self, provider_name: str) -> bool:
        """Check if stored token is expired or invalid."""
        pass


class NullStorage(TokenStorage):
    """Fallback storage that stores tokens in memory only. Tokens are lost on restart."""

    def __init__(self):
        self._tokens = {}

    def save(self, provider_name: str, tokens: TokenPair) -> None:
        logger.warning("Using in-memory token storage. Tokens will be lost on restart. Install keyring for persistent storage.")
        self._tokens[provider_name] = tokens

    def load(self, provider_name: str) -> Optional[TokenPair]:
        return self._tokens.get(provider_name)

    def delete(self, provider_name: str) -> None:
        self._tokens.pop(provider_name, None)

    def is_expired(self, provider_name: str) -> bool:
        return provider_name not in self._tokens


class KeyringStorage(TokenStorage):
    """OS-native credential storage via keyring (macOS Keychain, Windows Credential Locker, Linux Secret Service)."""

    SERVICE_NAME = "lynx_codex"

    def save(self, provider_name: str, tokens: TokenPair) -> None:
        import json
        import time
        data = json.dumps({
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": tokens.expires_in,
            "token_type": tokens.token_type,
            "issued_at": time.time()
        })
        keyring.set_password(self.SERVICE_NAME, f"{provider_name}_tokens", data)

    def load(self, provider_name: str) -> Optional[TokenPair]:
        import json
        data = keyring.get_password(self.SERVICE_NAME, f"{provider_name}_tokens")
        if not data:
            return None
        try:
            parsed = json.loads(data)
            return TokenPair(
                access_token=parsed["access_token"],
                refresh_token=parsed["refresh_token"],
                expires_in=parsed["expires_in"],
                token_type=parsed.get("token_type", "Bearer")
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def delete(self, provider_name: str) -> None:
        keyring.delete_password(self.SERVICE_NAME, f"{provider_name}_tokens")

    def is_expired(self, provider_name: str) -> bool:
        import json
        import time
        data = keyring.get_password(self.SERVICE_NAME, f"{provider_name}_tokens")
        if not data:
            return True
        try:
            parsed = json.loads(data)
            issued_at = parsed.get("issued_at", 0)
            expires_in = parsed.get("expires_in", 3600)
            # Consider expired 60 seconds before actual expiry to allow for refresh
            return (time.time() - issued_at) >= (expires_in - 60)
        except (json.JSONDecodeError, KeyError):
            return True


@runtime_checkable
class OAuthProvider(Protocol):
    """Protocol for OAuth providers. Implement to add new OAuth backends."""

    @property
    def name(self) -> str:
        """Provider identifier (e.g., 'openai', 'anthropic')."""
        ...

    @property
    def client_id(self) -> str:
        """OAuth client ID for this provider."""
        ...

    @property
    def scopes(self) -> list[str]:
        """Required OAuth scopes."""
        ...

    @property
    def authorization_url(self) -> str:
        """URL to direct user to for authorization."""
        ...

    @property
    def token_url(self) -> str:
        """URL to exchange auth code for tokens."""
        ...

    def generate_pkce(self) -> tuple[str, str]:
        """Generate PKCE verifier and challenge. Returns (verifier, challenge)."""
        ...

    def parse_callback(self, url: str) -> AuthCode:
        """Parse OAuth callback URL and extract auth code."""
        ...

    def exchange_code(self, code: AuthCode, pkce_verifier: str) -> TokenPair:
        """Exchange authorization code for tokens."""
        ...

    def refresh(self, refresh_token: str) -> TokenPair:
        """Refresh access token using refresh token."""
        ...


class OpenAIOAuthProvider:
    """OpenAI OAuth implementation using PKCE for secure CLI authentication."""

    AUTH_URL = "https://auth.openai.com/oauth/authorize"
    TOKEN_URL = "https://auth.openai.com/oauth/token"
    REDIRECT_URI = "http://127.0.0.1:8080/callback"

    def __init__(self, client_id: str, scopes: Optional[list[str]] = None):
        self._client_id = client_id
        self._scopes = scopes or ["model.request", "api.model.read", "offline_access"]

    @property
    def name(self) -> str:
        return "openai"

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def scopes(self) -> list[str]:
        return self._scopes

    @property
    def authorization_url(self) -> str:
        return self.AUTH_URL

    @property
    def token_url(self) -> str:
        return self.TOKEN_URL

    def generate_pkce(self) -> tuple[str, str]:
        import secrets
        import hashlib
        import base64

        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        return verifier, challenge

    def parse_callback(self, url: str) -> AuthCode:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        return AuthCode(code=qs["code"][0], state=qs.get("state", [None])[0])

    def exchange_code(self, code: AuthCode, pkce_verifier: str) -> TokenPair:
        import requests

        resp = requests.post(self.TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "code": code.code,
            "code_verifier": pkce_verifier,
            "redirect_uri": self.REDIRECT_URI,
        })
        resp.raise_for_status()
        data = resp.json()
        return TokenPair(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data.get("expires_in", 3600),
            token_type=data.get("token_type", "Bearer")
        )

    def refresh(self, refresh_token: str) -> TokenPair:
        import requests

        resp = requests.post(self.TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "refresh_token": refresh_token,
        })
        resp.raise_for_status()
        data = resp.json()
        return TokenPair(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_in=data.get("expires_in", 3600),
            token_type=data.get("token_type", "Bearer")
        )


class OAuthManager:
    """Orchestrates OAuth flow for any registered provider."""

    def __init__(self, storage: Optional[TokenStorage] = None):
        self._providers: dict[str, OAuthProvider] = {}
        if storage:
            self._storage = storage
        elif not _KEYRING_AVAILABLE:
            logger.warning("Keyring not available. Using in-memory token storage. Tokens will be lost on restart.")
            self._storage = NullStorage()
        else:
            self._storage = KeyringStorage()

    def register(self, provider: OAuthProvider) -> None:
        self._providers[provider.name] = provider

    def login_interactive(self, provider_name: str) -> None:
        """Full browser-based OAuth flow with local server."""
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from urllib.parse import urlencode

        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        pkce_verifier, pkce_challenge = provider.generate_pkce()
        state = os.urandom(16).hex()

        # Build auth URL
        params = urlencode({
            "client_id": provider.client_id,
            "response_type": "code",
            "redirect_uri": provider.TOKEN_URL.rsplit("/", 1)[0] + "/callback",
            "scope": " ".join(provider.scopes),
            "state": state,
            "code_challenge": pkce_challenge,
            "code_challenge_method": "S256",
        })
        auth_url = f"{provider.authorization_url}?{params}"

        # Local callback server
        auth_code_event = threading.Event()
        auth_code_result = [None]

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body>Authentication successful. Close this window.</body></html>")
                auth_code_result[0] = self.path
                auth_code_event.set()

            def log_message(self, *args): ...

        server = HTTPServer(("127.0.0.1", 8080), CallbackHandler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()

        # Open browser
        import webbrowser
        webbrowser.open(auth_url)

        # Wait for callback
        auth_code_event.wait(timeout=120)
        server.shutdown()
        thread.join()

        if not auth_code_result[0]:
            raise TimeoutError("OAuth timeout")

        # Exchange code for tokens
        auth_code = provider.parse_callback(f"http://127.0.0.1:8080{auth_code_result[0]}")
        tokens = provider.exchange_code(auth_code, pkce_verifier)
        self._storage.save(provider_name, tokens)

    def login_headless(self, provider_name: str) -> None:
        """Manual code paste flow for SSH/headless environments."""
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        print(f"Navigate to the authorization URL for {provider_name}:")
        pkce_verifier, pkce_challenge = provider.generate_pkce()
        params = urlencode({
            "client_id": provider.client_id,
            "response_type": "code",
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "scope": " ".join(provider.scopes),
            "code_challenge": pkce_challenge,
            "code_challenge_method": "S256",
        })
        print(f"{provider.authorization_url}?{params}")
        print("\nPaste the authorization code: ", end="", flush=True)
        code = input().strip()
        auth_code = AuthCode(code=code)
        tokens = provider.exchange_code(auth_code, pkce_verifier)
        self._storage.save(provider_name, tokens)

    def get_token(self, provider_name: str) -> Optional[str]:
        """Get valid access token, refreshing if needed."""
        tokens = self._storage.load(provider_name)
        if not tokens:
            return None

        if self._storage.is_expired(provider_name):
            provider = self._providers.get(provider_name)
            if provider and hasattr(provider, 'refresh'):
                tokens = provider.refresh(tokens.refresh_token)
                self._storage.save(provider_name, tokens)

        return tokens.access_token if tokens else None

    def logout(self, provider_name: str) -> None:
        """Remove stored credentials."""
        self._storage.delete(provider_name)
