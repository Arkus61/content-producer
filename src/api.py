"""Content Producer API — FastAPI application with routers."""

import logging
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db_client import db
from .auth import decode_supabase_token
from .compliance import audit_log

# ── Logging ──
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("content-producer")

# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Content Producer API started (Supabase mode)")
    yield
    logger.info("Content Producer API shutting down")

# ── App ──
app = FastAPI(
    title="Content Producer API",
    version="0.6.0-payment",
    description="AI SaaS for expert content creation — RF 152-FZ compliant, Supabase-backed",
    lifespan=lifespan,
)

# ── Middleware ──
# CORS: origins must be explicit when allow_credentials=True
_cors_origins = settings.cors_origins.split(",") if settings.cors_origins and settings.cors_origins != "*" else []
_cors_credentials = len(_cors_origins) > 0

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else ["*"],
    allow_credentials=_cors_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Audit log middleware
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if settings.enable_audit_logging and request.url.path.startswith("/api/"):
        path = request.url.path
        method = request.method
        user_id = None
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent", "")
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                payload = decode_supabase_token(auth_header.split(" ")[1])
                if payload:
                    user_id = payload.get("sub")
            try:
                await audit_log("api_request", str(uuid.uuid4()), method.lower(),
                               performed_by_user_id=user_id, ip_address=ip, user_agent=ua,
                               details={"path": path})
            except Exception:
                logger.warning("Audit logging failed for %s %s", method, path, exc_info=True)
    return response

# ── Routers ──
from .routers.auth import router as auth_router
from .routers.experts import router as experts_router
from .routers.interview import router as interview_router
from .routers.transcription import router as transcription_router
from .routers.content import router as content_router
from .routers.compliance import router as compliance_router
from .routers.social import router as social_router
from .routers.payment import router as payment_router
from .routers.pipeline import router as pipeline_router

app.include_router(auth_router)
app.include_router(experts_router)
app.include_router(interview_router)
app.include_router(transcription_router)
app.include_router(content_router)
app.include_router(compliance_router)
app.include_router(social_router)
app.include_router(payment_router)
app.include_router(pipeline_router)

# ── Health ──
@app.get("/health")
async def health():
    db_status = "ok"
    db_latency_ms = 0
    try:
        import time
        t0 = time.perf_counter()
        await db.expert_list(limit=1)
        db_latency_ms = round((time.perf_counter() - t0) * 1000)
    except Exception:
        db_status = "error"
    overall = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall,
        "version": "0.6.0-payment",
        "compliance": "152-FZ",
        "database": {"status": db_status, "latency_ms": db_latency_ms},
    }

@app.get("/")
async def root():
    return {"name": "Content Producer API", "version": "0.6.0", "docs": "/docs", "compliance": "152-FZ"}
