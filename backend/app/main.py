"""FastAPI application factory.

Run with:  uvicorn app.main:create_app --factory

Graceful shutdown (SIGTERM): uvicorn runs as PID 1 (exec-form CMD) so it receives
SIGTERM directly. On SIGTERM uvicorn stops accepting new connections and waits for
in-flight requests to finish (bounded by --timeout-graceful-shutdown); then our
lifespan shutdown below closes the DB pool and the Redis connection and the process
exits. In Kubernetes a preStop sleep runs first, so the pod has already left the
Service endpoints before it stops accepting connections - that is what makes
rolling updates drop zero requests.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.db import build_engine, build_session_factory
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.providers.cache import CacheStore, RedisLike, build_redis
from app.providers.triage.base import TriageProvider
from app.providers.triage.factory import build_triage_provider
from app.routes import complaints, health, meta, stats

logger = logging.getLogger("civicpulse")


def _field_name(loc: tuple[Any, ...] | list[Any]) -> str:
    # loc looks like ("body", "text") or ("query", "page_size"); drop the source.
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or "body"


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """The contract says 400 with a field-level error body (FastAPI's default is 422)."""
    errors = [{"field": _field_name(e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=400, content={"detail": "Validation failed", "errors": errors})


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    redis_client: RedisLike | None = None,
    triage_provider: TriageProvider | None = None,
) -> FastAPI:
    """Build the app. Tests inject an SQLite engine, fakeredis and a fake provider."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    engine = engine or build_engine(settings.sqlalchemy_url())
    client: Any = redis_client or build_redis(settings.redis_url)
    provider = triage_provider or build_triage_provider(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("startup", extra={"triage_provider": provider.name})
        yield
        # Runs after uvicorn has drained in-flight requests on SIGTERM.
        logger.info("shutdown: closing database pool and redis connection")
        engine.dispose()
        close = getattr(client, "close", None)
        if callable(close):
            close()
        logger.info("shutdown complete")

    app = FastAPI(
        title="CivicPulse API",
        version="1.0.0",
        description="Municipal complaint intake, AI triage and operations.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.cache = CacheStore(client)
    app.state.triage_provider = provider

    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(
        RequestValidationError, validation_error_handler  # type: ignore[arg-type]
    )

    app.include_router(health.router)
    app.include_router(complaints.router)
    app.include_router(stats.router)
    app.include_router(meta.router)
    return app
