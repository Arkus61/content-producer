"""Auth dependencies: extract user from JWT in request headers."""
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .auth import decode_token
from .db.engine import async_session_factory
from .db.models import User


security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Dependency: extract and validate JWT, return User object."""
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или просроченный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    token_type = payload.get("type", "access")
    if not user_id or token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден или деактивирован",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user
