"""GET /api/meta/providers - the triage observability surface."""

from fastapi import APIRouter, Depends, Request

from app.deps import get_cache
from app.providers.cache import CacheStore
from app.providers.triage.factory import AVAILABLE_PROVIDERS
from app.schemas import CacheStats, ProvidersOut, TriageOutcome

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/providers", response_model=ProvidersOut)
def providers(request: Request, cache: CacheStore = Depends(get_cache)) -> ProvidersOut:
    try:
        hits, misses = cache.triage_lookup_counts()
        recent = [TriageOutcome.model_validate(o) for o in cache.recent_outcomes()]
    except Exception:  # noqa: BLE001 - observability must not 500 when Redis blips
        hits, misses, recent = 0, 0, []
    lookups = hits + misses
    return ProvidersOut(
        active_provider=request.app.state.triage_provider.name,
        fallback_provider="rules",
        available_providers=list(AVAILABLE_PROVIDERS),
        triage_cache=CacheStats(
            hits=hits, misses=misses, hit_rate=round(hits / lookups, 3) if lookups else 0.0
        ),
        recent=recent,
    )
