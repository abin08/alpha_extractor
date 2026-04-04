from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.routes import jobs, target_config
from src.core.exceptions import (
    AlphaExtractorError,
    RateLimitExceeded,
    SourceOfflineError,
)
from src.core.logger import logger

app = FastAPI(
    title="Alpha Extractor API",
    description="Control Plane for the AI-driven market sentiment extraction pipeline.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Can be locked down to specific domains later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AlphaExtractorError)
async def alpha_extractor_exception_handler(request: Request, exc: AlphaExtractorError):
    """Maps domain-specific errors to structured JSON HTTP responses."""
    logger.error(f"Domain error: {exc}", extra={"path": request.url.path})

    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, RateLimitExceeded):
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, SourceOfflineError):
        status_code = status.HTTP_502_BAD_GATEWAY

    return JSONResponse(
        status_code=status_code,
        content={"error": exc.__class__.__name__, "message": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Fallback handler for unhandled server crashes."""
    logger.exception(f"Unhandled exception: {exc}", extra={"path": request.url.path})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred.",
        },
    )


app.include_router(target_config.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Verify application, logger, and database health."""
    logger.info("Health check endpoint pinged")
    try:
        # Ping the Postgres container
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    return {"status": "online", "database": db_status, "environment": "development"}
