"""Dependency wiring. Routes ask for a *service*; this module builds it.

The route never opens a database session itself - FastAPI calls get_session()
and closes the session after the response, and the session is handed to the
repository, which is the only code that uses it.
"""

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.providers.cache import CacheStore
from app.repositories.complaints import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.rate_limiter import RateLimiter
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_cache(request: Request) -> CacheStore:
    cache: CacheStore = request.app.state.cache
    return cache


def get_repository(session: Session = Depends(get_session)) -> ComplaintRepository:
    return ComplaintRepository(session)


def get_stats_service(
    repository: ComplaintRepository = Depends(get_repository),
    cache: CacheStore = Depends(get_cache),
    settings: Settings = Depends(get_settings_dep),
) -> StatsService:
    return StatsService(repository, cache, settings.stats_cache_ttl_seconds)


def get_triage_service(request: Request, cache: CacheStore = Depends(get_cache)) -> TriageService:
    settings: Settings = request.app.state.settings
    return TriageService(
        provider=request.app.state.triage_provider,
        cache=cache,
        cache_ttl_seconds=settings.triage_cache_ttl_seconds,
    )


def get_complaint_service(
    repository: ComplaintRepository = Depends(get_repository),
    triage: TriageService = Depends(get_triage_service),
    stats: StatsService = Depends(get_stats_service),
) -> ComplaintService:
    return ComplaintService(repository, triage, stats)


def get_rate_limiter(
    cache: CacheStore = Depends(get_cache), settings: Settings = Depends(get_settings_dep)
) -> RateLimiter:
    return RateLimiter(cache, settings.rate_limit_per_minute)


def client_ip(request: Request) -> str:
    """We sit behind nginx (Compose) or the Ingress (Kubernetes), so the real client
    is the first X-Forwarded-For entry. Without this every request would share the
    proxy's IP and one abusive user would rate-limit everybody."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
