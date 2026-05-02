"""Auth module — Supabase JWT validation + lazy user creation in Supabase DB."""
import jwt
from jwt import PyJWKClient
from typing import Optional
from fastapi import HTTPException, status

from .config import settings
from .db_client import db


def decode_supabase_token(token: str) -> Optional[dict]:
    """Validate a Supabase JWT (RS256) using Supabase's JWKS endpoint."""
    # Try RS256 via Supabase JWKS first
    if settings.supabase_url:
        try:
            jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/jwks"
            jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience="authenticated",
                options={"verify_exp": True},
            )
            return payload
        except Exception:
            pass
    # Fallback: HS256 with local secret (for tests / dev)
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret or "test-secret-key-32bytes-long-key!",
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
        return payload
    except Exception:
        return None


def get_user_id_from_payload(payload: dict) -> Optional[str]:
    return payload.get("sub")


def get_user_email_from_payload(payload: dict) -> Optional[str]:
    return payload.get("email")


def get_user_role_from_payload(payload: dict) -> str:
    return payload.get("role", "operator")


async def get_or_create_user(supabase_uid: str, email: str = "", full_name: str = "", role: str = "operator") -> dict:
    """Lazy-create user in Supabase 'users' table."""
    user = await db.user_get_by_supabase_uid(supabase_uid)
    if user:
        # Update stale fields
        needs_update = False
        for field, new_val in [("email", email), ("full_name", full_name), ("role", role)]:
            if new_val and user.get(field) != new_val:
                needs_update = True
        if needs_update:
            updates = {k: v for k, v in [("email", email), ("full_name", full_name), ("role", role)] if v}
            await db.user_update(user["id"], updates)
        return user

    # Create new
    new_user = await db.user_create({
        "supabase_uid": supabase_uid,
        "email": email or f"user-{supabase_uid[:8]}@local",
        "full_name": full_name or "Оператор",
        "role": role,
        "is_active": True,
    })
    return new_user


def require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
