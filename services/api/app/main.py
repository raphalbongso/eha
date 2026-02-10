"""EHA FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.config import Settings, get_settings
from app.dependencies import get_session_factory, init_db, shutdown_db
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging import LoggingMiddleware, setup_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import admin, ai, alerts, auth, automation, devices, drafts, events, gmail, preferences, rules, slack

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    setup_logging(debug=settings.debug)
    logger.info("Starting EHA API (env=%s)", settings.app_env)

    # Initialize database
    init_db(settings)

    yield

    # Shutdown
    await shutdown_db()
    logger.info("EHA API shutting down")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="EHA - Email Helper Agent",
        description="AI-powered email assistant with smart notifications and calendar integration",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middleware (order matters: outermost first)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    origins = settings.cors_origins
    allow_all = origins == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if not allow_all else [],
        allow_origin_regex=r".*" if allow_all else None,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        max_age=600,
    )

    # Routers
    prefix = settings.api_prefix
    app.include_router(auth.router, prefix=prefix)
    app.include_router(gmail.router, prefix=prefix)
    app.include_router(rules.router, prefix=prefix)
    app.include_router(alerts.router, prefix=prefix)
    app.include_router(ai.router, prefix=prefix)
    app.include_router(drafts.router, prefix=prefix)
    app.include_router(devices.router, prefix=prefix)
    app.include_router(events.router, prefix=prefix)
    app.include_router(preferences.router, prefix=prefix)
    app.include_router(automation.router, prefix=prefix)
    app.include_router(slack.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)

    @app.get("/")
    async def root():
        return {"status": "running", "service": "eha-api", "version": "1.0.0"}

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eha-api"}

    @app.get("/health/ready")
    async def health_ready():
        """Deep health check: verifies DB and Redis connectivity."""
        checks: dict = {}

        # Check PostgreSQL
        try:
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {type(e).__name__}"

        # Check Redis
        try:
            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            await r.ping()
            await r.aclose()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {type(e).__name__}"

        all_ok = all(v == "ok" for v in checks.values())
        status_code = 200 if all_ok else 503

        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=status_code,
            content={"status": "ready" if all_ok else "degraded", "checks": checks},
        )

    # Prometheus instrumentation
    instrumentator = Instrumentator(
        excluded_handlers=["/health", "/health/ready", "/docs", "/redoc", "/openapi.json", "/metrics"],
    )
    instrumentator.instrument(app)

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        """Prometheus metrics endpoint with multiprocess support."""
        from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, multiprocess

        multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        if multiproc_dir:
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            data = generate_latest(registry)
        else:
            data = generate_latest()

        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    return app


# Default app instance for uvicorn
app = create_app()
