"""
FastAPI application entrypoint for Agent 2 (Fashion Information Retrieval).
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import router
from app.models.product import Base
from app.api.dependencies import engine
from app.services.retrieval_service import get_retrieval_service

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("agent2_retrieval")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Agent 2 service...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified.")
    except Exception as e:
        logger.warning(f"Database initialization notice: {e}")

    try:
        service = get_retrieval_service()
        logger.info(f"Retrieval service ready with {len(service.products)} products.")
    except Exception as e:
        logger.warning(f"Retrieval service preload notice: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Agent 2 service...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="FASHORA Agent 2: Fashion Information Retrieval Agent using Hybrid BM25 + Semantic Search",
    lifespan=lifespan
)

# Hardened CORS Middleware: use explicit allowed origins, never wildcard with credentials
cors_origins = settings.cors_origins_list
allow_creds = True
if "*" in cors_origins:
    allow_creds = False  # Browsers forbid allow_credentials=True with wildcard origin

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers to prevent data / stack trace leakage
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error in request payload", "errors": exc.errors()},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log the real exception internally without exposing stack trace or DB details to the client
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred. Request could not be completed."},
    )

# Include API routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
