"""Auth dependencies — extract Supabase user from JWT, lazy-create in DB."""
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .auth import decode_supabase_token, get_user_id_from_payload, get_or_create_user_from_supabase
from .db.engine import async_session_factory
from .db.models import User


security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Dependency: validate Supabase JWT, lazy-create User, return User object."""
    token = credentials.credentials
    payload = decode_supabase_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или просроченный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase_uid = get_user_id_from_payload(payload)
    if not supabase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email", "")
    full_name = payload.get("user_metadata", {}).get("full_name", "")
    role = payload.get("role", "operator")

    async with async_session_factory() as session:
        user = await get_or_create_user_from_supabase(
            session, supabase_uid, email, full_name, role
        )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь деактивирован",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user
