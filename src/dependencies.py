"""Auth dependencies — extract Supabase user from JWT, lazy-create in users table."""
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .auth import decode_supabase_token, get_user_id_from_payload, get_or_create_user


security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency: validate Supabase JWT, lazy-create User row, return user dict."""
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
    role = payload.get("app_metadata", {}).get("role") or payload.get("role", "operator")

    user = await get_or_create_user(supabase_uid, email, full_name, role)
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь деактивирован",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user


async def require_expert_owner(expert_id: str, user: dict) -> None:
    """Verify user owns the expert record (or is admin)."""
    from .db_client import db
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(status_code=404, detail="Expert not found")
    if user.get("role") != "admin" and e.get("owner_user_id") != user.get("id"):
        raise HTTPException(status_code=403, detail="Нет доступа к записи эксперта")
