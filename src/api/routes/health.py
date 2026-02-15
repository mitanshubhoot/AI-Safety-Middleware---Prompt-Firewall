"""Health check endpoints."""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src import __version__
from src.config import get_settings
from src.core.cache.redis_client import get_redis_client
from src.core.models.schemas import HealthResponse
from src.db.session import get_db

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """Health check endpoint.

    Returns:
        HealthResponse with service status
    """
    # Check database
    db_status = "healthy"
    try:
        from sqlalchemy import text

        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Check Redis
    redis_status = "healthy"
    try:
        redis_client = await get_redis_client()
        await redis_client.client.ping()
    except Exception:
        redis_status = "unhealthy"

    # Overall status
    status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "unhealthy"

    return HealthResponse(
        status=status,
        version=__version__,
        environment=settings.ENVIRONMENT,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.utcnow(),
    )


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness probe for Kubernetes.

    Returns:
        Simple ready status
    """
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Liveness probe for Kubernetes.

    Returns:
        Simple alive status
    """
    return {"status": "alive"}
