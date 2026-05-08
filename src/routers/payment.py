"""Payment & subscription endpoints."""
from fastapi import APIRouter, HTTPException, Depends, Request
from ..config import settings
from ..db_client import db
from ..dependencies import get_current_user
from ..payment import (
    SubscriptionService, CreateSubscriptionRequest,
    ProdamusWebhookHandler, ProdamusClient,
)

router = APIRouter(prefix="/api", tags=["payment"])

_subscription_service: SubscriptionService | None = None


def _get_subscription_service() -> SubscriptionService:
    global _subscription_service
    if _subscription_service is None:
        prodamus = None
        if settings.prodamus_api_key:
            prodamus = ProdamusClient()
        _subscription_service = SubscriptionService(
            db_client=db if settings.supabase_url else None,
            prodamus=prodamus,
        )
    return _subscription_service


@router.post("/subscriptions")
async def create_subscription(req: CreateSubscriptionRequest, user: dict = Depends(get_current_user)):
    req.user_id = user.get("id", req.user_id)
    svc = _get_subscription_service()
    return await svc.create_subscription(req)


@router.get("/subscriptions/current")
async def get_current_subscription(user: dict = Depends(get_current_user)):
    svc = _get_subscription_service()
    sub = await svc.get_subscription(user.get("id", ""))
    if not sub:
        return {"status": "none", "tier": "free", "message": "No subscription found — using free tier"}
    return {
        "id": sub.id, "tier": sub.tier, "status": sub.status,
        "started_at": sub.started_at, "expires_at": sub.expires_at,
        "auto_renew": sub.auto_renew,
    }


@router.post("/payment/webhook/prodamus")
async def prodamus_webhook(request: Request):
    import logging
    logger = logging.getLogger("content-producer")
    from ..payment import ProdamusWebhookPayload

    raw_body = await request.body()
    signature = request.headers.get("X-Signature")
    handler = ProdamusWebhookHandler(settings.prodamus_secret_key)

    if settings.prodamus_secret_key:
        if not handler.verify(raw_body, signature):
            logger.warning("Prodamus webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        form = await request.form()
        payload = handler.parse(dict(form))
    except Exception as exc:
        logger.error("Prodamus webhook parse error: %s", exc)
        raise HTTPException(status_code=422, detail="Invalid payload")

    svc = _get_subscription_service()
    success = await svc.handle_webhook(payload)
    if not success:
        raise HTTPException(status_code=400, detail="Webhook processing failed")
    return {"status": "ok"}


@router.get("/payment/transactions")
async def list_transactions(limit: int = 20, skip: int = 0, user: dict = Depends(get_current_user)):
    result = await db.table("payment_transactions")\
        .select("*")\
        .eq("user_id", user.get("id", ""))\
        .order("created_at", desc=True)\
        .range(skip, skip + limit - 1)\
        .execute()
    rows = result.data if hasattr(result, "data") else []
    return {"items": rows, "total": len(rows), "skip": skip, "limit": limit}
