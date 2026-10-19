"""
MyGovt Backend — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import check_db_health
from app.core.logging import setup_logging
from app.api.v1 import router as api_v1_router

setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("MyGovt backend starting", env=settings.APP_ENV)
    try:
        await check_db_health()
        logger.info("Database connection verified")
    except Exception as e:
        logger.error("Database health check failed at startup", error=str(e))
    yield
    logger.info("MyGovt backend shutting down")


app = FastAPI(
    title="MyGovt API",
    description="AI-Powered Citizen Intelligence & State Governance Platform",
    version="1.0.0",
    # API docs are an information leak in production; keep them for development/test only
    docs_url=None if settings.APP_ENV.lower() == "production" else "/api/docs",
    redoc_url=None if settings.APP_ENV.lower() == "production" else "/api/redoc",
    openapi_url=None if settings.APP_ENV.lower() == "production" else "/api/openapi.json",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.APP_CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID, body-size cap and security headers ────────────
MAX_JSON_BODY_BYTES = 1 * 1024 * 1024           # 1 MiB for ordinary API calls
MAX_UPLOAD_BODY_BYTES = 55 * 1024 * 1024        # evidence uploads (<= 50 MB file + multipart overhead)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(self), camera=(), microphone=()",
}


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    limit = MAX_UPLOAD_BODY_BYTES if request.url.path.endswith("/evidence") else MAX_JSON_BODY_BYTES
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        return JSONResponse(status_code=413, content={"code": "PAYLOAD_TOO_LARGE",
                                                      "message": "Request body too large.", "request_id": request_id})
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if request.url.path.startswith("/api/v1/auth"):
        response.headers["Cache-Control"] = "no-store"      # never cache tokens / identity
    return response


# ── Exception handlers ────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred. Please try again.",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# ── Health check ─────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint."""
    from app.core.health import get_health_status
    return await get_health_status()


# ── API routes ───────────────────────────────────────────────
app.include_router(api_v1_router, prefix="/api/v1")
