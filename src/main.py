"""FastAPI application entry point."""
import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src import __version__
from src.api.routes import health, policies, prompts
from src.config import get_settings
from src.core.cache.redis_client import close_redis_client, get_redis_client
from src.core.cache.vector_store import close_vector_store
from src.db.session import close_db, init_db
from src.utils.exceptions import AIFirewallException
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)

settings = get_settings()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Args:
        app: FastAPI application

    Yields:
        None
    """
    # Startup
    logger.info(
        "starting_application",
        version=__version__,
        environment=settings.ENVIRONMENT,
    )

    try:
        # Initialize database
        await init_db()
        logger.info("database_initialized")

        # Initialize Redis
        await get_redis_client()
        logger.info("redis_initialized")

        logger.info("application_started")

    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("shutting_down_application")

    try:
        # Close Redis connections
        await close_redis_client()
        await close_vector_store()
        logger.info("redis_connections_closed")

        # Close database connections
        await close_db()
        logger.info("database_connections_closed")

        logger.info("application_shutdown_complete")

    except Exception as e:
        logger.error("shutdown_failed", error=str(e))


# Create FastAPI app
app = FastAPI(
    title="AI Safety Middleware - Prompt Firewall",
    description="Enterprise-grade AI prompt firewall for real-time LLM safety validation",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Middleware
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next: Any) -> Response:
    """Add request ID to all requests.

    Args:
        request: FastAPI request
        call_next: Next middleware

    Returns:
        Response with request ID header
    """
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next: Any) -> Response:
    """Log all requests.

    Args:
        request: FastAPI request
        call_next: Next middleware

    Returns:
        Response
    """
    import time

    start_time = time.time()

    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown",
    )

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000

    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(AIFirewallException)
async def aifw_exception_handler(request: Request, exc: AIFirewallException) -> JSONResponse:
    """Handle custom application exceptions.

    Args:
        request: FastAPI request
        exc: AIFirewallException

    Returns:
        JSONResponse with error details
    """
    logger.error(
        "aifw_exception",
        error=exc.message,
        details=exc.details,
        path=request.url.path,
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions.

    Args:
        request: FastAPI request
        exc: Exception

    Returns:
        JSONResponse with error message
    """
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns:
        Response with Prometheus metrics
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# Include routers
app.include_router(health.router, prefix="")
app.include_router(prompts.router, prefix=settings.API_V1_PREFIX)
app.include_router(policies.router, prefix=settings.API_V1_PREFIX)


# Root endpoint
@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Welcome message
    """
    return {
        "message": "AI Safety Middleware - Prompt Firewall",
        "version": __version__,
        "docs": "/docs",
    }


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=1 if settings.DEBUG else settings.WORKERS,
    )
