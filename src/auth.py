"""Auth module — Supabase JWT validation only. No passwords."""
import jwt
from jwt import PyJWKClient
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from .config import settings
from .db.models import User


def decode_supabase_token(token: str) -> Optional[dict]:
    """Validate a Supabase JWT (RS256) using Supabase's JWKS endpoint."""
    try:
        # Supabase uses RS256 + JWKS
        jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/jwks"
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="authenticated",  # Supabase default
            options={"verify_exp": True},
        )
        return payload
    except Exception:
        # Fallback: if supabase_url is not set (tests), try HS256 with local secret
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret or "test-secret",
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
            return payload
        except Exception:
            return None


def get_user_id_from_payload(payload: dict) -> Optional[str]:
    """Extract Supabase user UUID from JWT payload."""
    # Supabase JWT 'sub' is the user's UUID in auth.users
    return payload.get("sub")


def get_user_email_from_payload(payload: dict) -> Optional[str]:
    return payload.get("email")


def get_user_role_from_payload(payload: dict) -> str:
    """Read custom claim 'role' if set, else default to operator."""
    return payload.get("role", "operator")


async def get_or_create_user_from_supabase(
    session: AsyncSession,
    supabase_uid: str,
    email: str,
    full_name: str = "",
    role: str = "operator",
) -> User:
    """Lazy-create a local User record from Supabase auth data."""
    result = await session.execute(select(User).where(User.supabase_uid == supabase_uid))
    user = result.scalar_one_or_none()
    if user:
        # Update email if changed
        if email and user.email != email:
            user.email = email
        if full_name and user.full_name != full_name:
            user.full_name = full_name
        await session.commit()
        return user

    user = User(
        supabase_uid=supabase_uid,
        email=email or f"user-{supabase_uid[:8]}@local",
        full_name=full_name or "Оператор",
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
