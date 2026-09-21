"""
FASHORA — Agent 1: Style & Wardrobe Intelligence Agent
FastAPI Application Entrypoint.
"""

import sys
from pathlib import Path

# Allow importing the repo-level `shared` package when running from agents/agent1_wardrobe
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import logger
from app.models.database import init_db, SessionLocal
from app.utils.seed_data import seed_database_if_empty
from app.api import auth, wardrobe, analysis, agent, security


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION} on port {settings.PORT}...")
    init_db()
    if settings.SEED_DEMO_DATA:
        db = SessionLocal()
        try:
            seed_database_if_empty(db)
            logger.info("Demo seed enabled — demo user / sample wardrobe ready if DB was empty.")
        finally:
            db.close()
    else:
        logger.info("Database initialized (demo seed disabled).")
    yield
    logger.info("Shutting down Agent 1 service.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="""
# FASHORA — Agent 1: Style & Wardrobe Intelligence Agent

Agent 1 is the dedicated Wardrobe Intelligence agent in the FASHORA multi-agent architecture.
It is responsible for:
1. **Understanding what the user owns** (Computer vision analysis of uploaded clothing photos).
2. **Understanding what the user wants** (Natural language fashion request understanding via NLP & LLM structured extraction).
3. **Determining required clothing categories** for the given occasion and desired style.
4. **Detecting missing categories** needed to complete the outfit.
5. **Evaluating wardrobe compatibility** (color harmony, style consistency, occasion suitability).
6. **Emitting a strict, validated JSON contract** for downstream **Agent 2 (Product Retrieval)**, **Agent 3 (Budget Optimizer)**, and **Agent 4 (Decision Agent)**.

### Architectural Boundaries
- Agent 1 **does NOT** search external products (owned by Agent 2).
- Agent 1 **does NOT** optimize budgets or calculate purchase baskets (owned by Agent 3).
- Agent 1 **does NOT** make final outfit purchasing decisions (owned by Agent 4).
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing and structured correlation middleware
@app.middleware("http")
async def add_correlation_and_timing_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response


# Mount static uploads directory for serving clothing images
upload_dir_path = Path(settings.UPLOAD_DIR).resolve()
upload_dir_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir_path)), name="uploads")

# Include Routers
app.include_router(auth.router)
app.include_router(wardrobe.router)
app.include_router(analysis.router)
app.include_router(agent.router)
app.include_router(security.router)


@app.get("/", tags=["Root"])
def root():
    """Service status and quick links."""
    return {
        "service": settings.APP_NAME,
        "status": "operational",
        "version": settings.VERSION,
        "docs": "/docs",
        "agent_schema": "/api/agent/schema",
        "agent_status": "/api/agent/status"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
