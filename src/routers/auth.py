"""Auth endpoints."""
from fastapi import APIRouter, Depends
from ..config import settings
from ..db_client import db
from ..db.schemas import UserResponse, UserUpdate
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    from datetime import datetime, timezone
    return UserResponse(
        id=user.get("id", ""), email=user.get("email", ""),
        full_name=user.get("full_name", ""), role=user.get("role", "operator"),
        email_verified=user.get("email_verified", False),
        phone_verified=user.get("phone_verified", False),
        last_login_at=user.get("last_login_at"),
        created_at=user.get("created_at", datetime.now(timezone.utc).isoformat()),
    )


@router.patch("/me")
async def update_me(req: UserUpdate, user: dict = Depends(get_current_user)):
    updates = {}
    if req.full_name is not None:
        updates["full_name"] = req.full_name
    if req.phone is not None:
        updates["phone"] = req.phone
    if updates:
        await db.user_update(user.get("id"), updates)
    return {"status": "updated"}
