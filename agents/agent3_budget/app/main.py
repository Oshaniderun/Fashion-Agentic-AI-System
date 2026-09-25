"""
FASHORA — Budget & Purchase Planning service (internal codename Agent 3).
FastAPI entrypoint on port 8003.

Same conventions as Agents 1/2: root-.env config, shared PostgreSQL database,
Agent 1 JWT / shared service-token auth, /health probe.
"""

import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Config FIRST — populates os.environ DATABASE_URL for the shared DB layer.
from app.core.config import get_settings  # noqa: E402

settings = get_settings()

from fastapi import FastAPI, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import app.models  # noqa: E402,F401 — register budget_* tables on the shared Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("budget_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.db import init_db

    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION} on port {settings.SERVICE_PORT}...")
    init_db()  # additive: creates budget_* tables in the shared database
    logger.info("Shared database initialized (budget tables registered).")
    yield
    logger.info("Shutting down budget service.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Budget calculation, purchase minimization, combination optimization, "
        "cost evaluation and comparison for outfit recommendations. "
        "Consumes Agent 1 wardrobe context and Agent 2 retrieved products; "
        "emits structured budget decisions for Agent 4."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_and_timing(request: Request, call_next):
    start = time.perf_counter()
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Response-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))
    return response


@app.get("/health", tags=["Ops"])
def health():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.VERSION}


@app.exception_handler(Exception)
async def masked_internal_error(request: Request, exc: Exception):
    """Never leak stack traces or internal state to clients."""
    from fastapi.responses import JSONResponse

    from app.core.security import scrub_pii

    logger.error(f"Unhandled error on {request.url.path}: {scrub_pii(str(exc))}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred while processing the budget request."},
    )


@app.get("/", tags=["Root"])
def root():
    return {
        "service": settings.APP_NAME,
        "status": "operational",
        "version": settings.VERSION,
        "currency": settings.CURRENCY,
        "docs": "/docs",
    }


from app.api.routes import budget_router  # noqa: E402

app.include_router(budget_router)
