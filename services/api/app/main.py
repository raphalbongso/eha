"""EHA FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.dependencies import init_db, shutdown_db
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging import LoggingMiddleware, setup_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import admin, ai, alerts, auth, devices, drafts, events, gmail, rules

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
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
    )

    # Middleware (order matters: outermost first)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    app.include_router(admin.router, prefix=prefix)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eha-api"}

    @app.get("/metrics")
    async def metrics():
        """Prometheus-compatible metrics endpoint stub.

        In production, integrate with prometheus_fastapi_instrumentator.
        """
        return {"status": "ok", "detail": "Metrics endpoint - integrate prometheus_fastapi_instrumentator"}

    return app


# Default app instance for uvicorn
app = create_app()
