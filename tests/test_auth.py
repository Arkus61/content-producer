"""Tests for auth module — JWT decoding, user creation, admin checks."""

import pytest
import jwt
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from src.auth import (
    decode_supabase_token,
    get_user_id_from_payload,
    get_user_email_from_payload,
    get_user_role_from_payload,
    get_or_create_user,
    require_admin,
)
from src.db_client import db, _mem


@pytest.fixture(autouse=True)
def reset_memory():
    _mem.__init__()
    yield
    _mem.__init__()


# ── decode_supabase_token (RS256 via Supabase JWKS) ────────

class TestDecodeTokenRS256:
    @pytest.mark.asyncio
    @patch("src.auth.settings")
    @patch("src.auth.PyJWKClient")
    async def test_rs256_success(self, mock_jwks_client, mock_settings):
        mock_settings.supabase_url = "https://xxx.supabase.co"
        mock_settings.debug = False

        # Create a real RS256 token with a known payload
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()

        signing_key_mock = MagicMock()
        signing_key_mock.key = public_key
        jwks_instance = MagicMock()
        jwks_instance.get_signing_key_from_jwt.return_value = signing_key_mock
        mock_jwks_client.return_value = jwks_instance

        payload_data = {"sub": "user-123", "email": "test@example.com", "role": "operator", "aud": "authenticated"}
        token = jwt.encode(payload_data, private_key, algorithm="RS256")

        result = decode_supabase_token(token)
        assert result is not None
        assert result["sub"] == "user-123"
        assert result["email"] == "test@example.com"


# ── decode_supabase_token (HS256 fallback) ────────────────

class TestDecodeTokenHS256:
    @patch("src.auth.settings")
    def test_hs256_fallback_success(self, mock_settings):
        mock_settings.supabase_url = ""
        mock_settings.debug = True
        mock_settings.supabase_jwt_secret = "test-secret-key-32bytes!!"

        token = jwt.encode(
            {"sub": "user-789", "role": "admin"},
            "test-secret-key-32bytes!!",
            algorithm="HS256",
        )
        result = decode_supabase_token(token)
        assert result is not None
        assert result["sub"] == "user-789"
        assert result["role"] == "admin"

    @patch("src.auth.settings")
    def test_hs256_fails_without_secret(self, mock_settings):
        mock_settings.supabase_url = ""
        mock_settings.supabase_jwt_secret = ""

        token = jwt.encode({"sub": "x"}, "wrong", algorithm="HS256")
        result = decode_supabase_token(token)
        assert result is None

    @patch("src.auth.settings")
    def test_invalid_token_returns_none(self, mock_settings):
        mock_settings.supabase_url = ""
        mock_settings.supabase_jwt_secret = ""

        result = decode_supabase_token("not.a.valid.token")
        assert result is None


# ── Payload helpers ─────────────────────────────────────────

class TestPayloadHelpers:
    def test_get_user_id(self):
        assert get_user_id_from_payload({"sub": "abc"}) == "abc"
        assert get_user_id_from_payload({}) is None

    def test_get_user_email(self):
        assert get_user_email_from_payload({"email": "a@b.com"}) == "a@b.com"
        assert get_user_email_from_payload({}) is None

    def test_get_user_role(self):
        assert get_user_role_from_payload({"role": "admin"}) == "admin"
        assert get_user_role_from_payload({}) == "operator"  # default


# ── get_or_create_user ─────────────────────────────────────

class TestGetOrCreateUser:
    @pytest.mark.asyncio
    async def test_creates_new_user(self):
        user = await get_or_create_user("suid-new", "new@test.com", "New User")
        assert user["supabase_uid"] == "suid-new"
        assert user["email"] == "new@test.com"
        assert user["full_name"] == "New User"
        assert user["is_active"] is True

    @pytest.mark.asyncio
    async def test_returns_existing_user(self):
        await db.user_create({
            "id": "u-1", "supabase_uid": "suid-exist",
            "email": "exist@test.com", "full_name": "Exist", "role": "operator",
        })
        user = await get_or_create_user("suid-exist")
        assert user["id"] == "u-1"
        assert user["email"] == "exist@test.com"

    @pytest.mark.asyncio
    async def test_updates_stale_fields(self):
        await db.user_create({
            "id": "u-1", "supabase_uid": "suid-stale",
            "email": "old@test.com", "full_name": "Old", "role": "operator",
        })
        user = await get_or_create_user("suid-stale", "new@test.com", "New", "admin")
        assert user["email"] == "new@test.com"
        assert user["full_name"] == "New"
        assert user["role"] == "admin"


# ── require_admin ───────────────────────────────────────────

class TestRequireAdmin:
    def test_admin_passes(self):
        # Should not raise
        require_admin({"role": "admin"})

    def test_non_admin_raises(self):
        with pytest.raises(HTTPException) as exc:
            require_admin({"role": "operator"})
        assert exc.value.status_code == 403

    def test_missing_role_raises(self):
        with pytest.raises(HTTPException) as exc:
            require_admin({})
        assert exc.value.status_code == 403
