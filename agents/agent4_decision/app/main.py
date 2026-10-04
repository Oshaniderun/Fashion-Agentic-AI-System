"""
FASHORA — Outfit Decision & Personalization service (internal codename Agent 4).
FastAPI entrypoint on port 8004.

Same conventions as Agents 1/2/3: root-.env config, Agent 1 JWT / shared
service-token auth, /health probe, security headers, masked errors.

Agent 4 is the decision layer: it combines the validated outputs of Agents
1-3 into a single complete outfit recommendation with a confidence score and
an explanation. It never re-derives another agent's work, and it stores only a
hash-keyed decision audit row (no request content, no user data).
"""

import logging
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.core.config import get_settings  # noqa: E402

settings = get_settings()

from fastapi import FastAPI, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("decision_service")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Combines validated Agent 1 (requirements + wardrobe), Agent 2 "
        "(retrieved products) and Agent 3 (budget-feasible options) output to "
        "decide the final complete outfit, with confidence and explanation. "
        "Never recomputes budgets, never invents products."
    ),
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
        content={"detail": "An internal error occurred while making the outfit decision."},
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


from app.api.routes import decision_router  # noqa: E402
from app.api.audit_routes import audit_router  # noqa: E402

app.include_router(decision_router)
app.include_router(audit_router)
