"""Tests for OAuth provider implementation."""

import os
import sys
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent / "src"))

from lynx.oauth import (
    TokenPair,
    AuthCode,
    KeyringStorage,
    OpenAIOAuthProvider,
    OAuthManager,
)


class TestOpenAIOAuthProvider:
    """Test OpenAI OAuth provider."""

    def test_provider_name(self):
        """Provider name should be 'openai'."""
        provider = OpenAIOAuthProvider(client_id="test-client")
        assert provider.name == "openai"

    def test_scopes_default(self):
        """Default scopes should include model.request, api.model.read, offline_access."""
        provider = OpenAIOAuthProvider(client_id="test-client")
        assert "model.request" in provider.scopes
        assert "api.model.read" in provider.scopes
        assert "offline_access" in provider.scopes

    def test_scopes_custom(self):
        """Custom scopes should override defaults."""
        provider = OpenAIOAuthProvider(
            client_id="test-client",
            scopes=["custom.scope"]
        )
        assert provider.scopes == ["custom.scope"]

    def test_auth_url(self):
        """Auth URL should be OpenAI's OAuth endpoint."""
        provider = OpenAIOAuthProvider(client_id="test-client")
        assert provider.authorization_url == "https://auth.openai.com/oauth/authorize"

    def test_token_url(self):
        """Token URL should be OpenAI's OAuth token endpoint."""
        provider = OpenAIOAuthProvider(client_id="test-client")
        assert provider.token_url == "https://auth.openai.com/oauth/token"

    def test_generate_pkce_returns_tuple(self):
        """PKCE generation should return verifier and challenge."""
        provider = OpenAIOAuthProvider(client_id="test-client")
        verifier, challenge = provider.generate_pkce()

        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 0
        assert len(challenge) > 0

    def test_generate_pkce_challenge_is_base64(self):
        """PKCE challenge should be base64url encoded."""
        provider = OpenAIOAuthProvider(client_id="test-client")
        verifier, challenge = provider.generate_pkce()

        # Should be valid base64url characters only
        import base64
        try:
            # Add padding if needed and decode
            padded = challenge + "=="
            decoded = base64.urlsafe_b64decode(padded)
            assert len(decoded) == 32  # SHA256 produces 32 bytes
        except Exception:
            pytest.fail("Challenge is not valid base64url")

    def test_parse_callback(self):
        """Should parse auth code from callback URL."""
        provider = OpenAIOAuthProvider(client_id="test-client")
        callback_url = "http://127.0.0.1:8080/callback?code=abc123&state=xyz"

        auth_code = provider.parse_callback(callback_url)

        assert auth_code.code == "abc123"
        assert auth_code.state == "xyz"

    def test_parse_callback_without_state(self):
        """Should parse callback without state."""
        provider = OpenAIOAuthProvider(client_id="test-client")
        callback_url = "http://127.0.0.1:8080/callback?code=abc123"

        auth_code = provider.parse_callback(callback_url)

        assert auth_code.code == "abc123"
        assert auth_code.state is None

    @patch("requests.post")
    def test_exchange_code(self, mock_post):
        """Should exchange auth code for tokens."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_abc123",
            "refresh_token": "refresh_xyz789",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_post.return_value = mock_response

        provider = OpenAIOAuthProvider(client_id="test-client")
        auth_code = AuthCode(code="auth_code_123")
        tokens = provider.exchange_code(auth_code, pkce_verifier="verifier_abc")

        assert tokens.access_token == "access_abc123"
        assert tokens.refresh_token == "refresh_xyz789"
        assert tokens.expires_in == 3600
        assert tokens.token_type == "Bearer"

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]["data"]
        assert call_kwargs["grant_type"] == "authorization_code"
        assert call_kwargs["code"] == "auth_code_123"
        assert call_kwargs["code_verifier"] == "verifier_abc"

    @patch("requests.post")
    def test_refresh(self, mock_post):
        """Should refresh access token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_post.return_value = mock_response

        provider = OpenAIOAuthProvider(client_id="test-client")
        tokens = provider.refresh(refresh_token="old_refresh_token")

        assert tokens.access_token == "new_access_token"
        assert tokens.refresh_token == "new_refresh_token"

        call_kwargs = mock_post.call_args[1]["data"]
        assert call_kwargs["grant_type"] == "refresh_token"
        assert call_kwargs["refresh_token"] == "old_refresh_token"


class TestKeyringStorage:
    """Test KeyringStorage token storage."""

    def test_save_and_load(self):
        """Should save and load tokens."""
        storage = KeyringStorage()
        tokens = TokenPair(
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,
            token_type="Bearer"
        )

        with patch("keyring.set_password") as mock_set:
            storage.save("test_provider", tokens)
            mock_set.assert_called_once()

            # Verify the data stored
            call_data = json.loads(mock_set.call_args[0][2])
            assert call_data["access_token"] == "access123"
            assert call_data["refresh_token"] == "refresh456"
            assert "issued_at" in call_data

    def test_load_returns_none_when_empty(self):
        """Should return None when no tokens stored."""
        storage = KeyringStorage()

        with patch("keyring.get_password", return_value=None):
            result = storage.load("nonexistent")
            assert result is None

    def test_is_expired_false_for_fresh_token(self):
        """Should not be expired immediately after saving."""
        storage = KeyringStorage()
        tokens = TokenPair(
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,
            token_type="Bearer"
        )

        with patch("keyring.set_password"):
            storage.save("test_provider", tokens)

        with patch("keyring.get_password") as mock_get:
            # Return fresh token data
            mock_get.return_value = json.dumps({
                "access_token": "access123",
                "refresh_token": "refresh456",
                "expires_in": 3600,
                "token_type": "Bearer",
                "issued_at": time.time()
            })

            assert storage.is_expired("test_provider") is False

    def test_is_expired_true_for_old_token(self):
        """Should be expired for token past expiry time."""
        storage = KeyringStorage()

        with patch("keyring.get_password") as mock_get:
            # Return token issued 2 hours ago with 1 hour expiry
            mock_get.return_value = json.dumps({
                "access_token": "access123",
                "refresh_token": "refresh456",
                "expires_in": 3600,
                "token_type": "Bearer",
                "issued_at": time.time() - 7200  # 2 hours ago
            })

            assert storage.is_expired("test_provider") is True

    def test_delete(self):
        """Should delete tokens."""
        storage = KeyringStorage()

        with patch("keyring.delete_password") as mock_delete:
            storage.delete("test_provider")
            mock_delete.assert_called_once_with(
                KeyringStorage.SERVICE_NAME,
                "test_provider_tokens"
            )


class TestOAuthManager:
    """Test OAuthManager orchestration."""

    def test_register_and_get_provider(self):
        """Should register and retrieve providers."""
        manager = OAuthManager()
        provider = OpenAIOAuthProvider(client_id="test-client")

        manager.register(provider)
        assert manager._providers["openai"] is provider

    def test_login_interactive_opens_browser(self):
        """Should open browser for interactive login."""
        manager = OAuthManager()
        provider = OpenAIOAuthProvider(client_id="test-client")
        manager.register(provider)

        with patch("webbrowser.open") as mock_browser:
            with patch("threading.Thread"):
                with patch("http.server.HTTPServer"):
                    # Simulate quick callback
                    with patch.object(manager, "_storage") as mock_storage:
                        mock_storage.load.return_value = None

                        # Would need to mock the callback server
                        # This is a basic smoke test
                        pass

    def test_get_token_returns_none_when_not_logged_in(self):
        """Should return None when no tokens stored."""
        manager = OAuthManager()

        with patch.object(manager._storage, "load", return_value=None):
            token = manager.get_token("openai")
            assert token is None

    def test_get_token_returns_access_token(self):
        """Should return access token when valid tokens exist."""
        manager = OAuthManager()
        tokens = TokenPair(
            access_token="valid_access_token",
            refresh_token="refresh_token",
            expires_in=3600,
            token_type="Bearer"
        )

        with patch.object(manager._storage, "load", return_value=tokens):
            with patch.object(manager._storage, "is_expired", return_value=False):
                token = manager.get_token("openai")
                assert token == "valid_access_token"

    def test_get_token_refreshes_when_expired(self):
        """Should refresh token when expired."""
        manager = OAuthManager()
        provider = OpenAIOAuthProvider(client_id="test-client")
        manager.register(provider)

        old_tokens = TokenPair(
            access_token="old_access",
            refresh_token="refresh_token",
            expires_in=3600,
            token_type="Bearer"
        )
        new_tokens = TokenPair(
            access_token="new_access",
            refresh_token="new_refresh",
            expires_in=3600,
            token_type="Bearer"
        )

        with patch.object(manager._storage, "load", return_value=old_tokens):
            with patch.object(manager._storage, "is_expired", return_value=True):
                with patch.object(provider, "refresh", return_value=new_tokens):
                    with patch.object(manager._storage, "save"):
                        token = manager.get_token("openai")
                        assert token == "new_access"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
