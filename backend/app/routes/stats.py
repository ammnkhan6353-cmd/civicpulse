"""GET /api/stats - aggregates with an X-Cache: HIT|MISS header."""

from fastapi import APIRouter, Depends, Response

from app.deps import get_stats_service
from app.schemas import StatsOut
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(response: Response, service: StatsService = Depends(get_stats_service)) -> StatsOut:
    result = service.get()
    response.headers["X-Cache"] = "HIT" if result.cache_hit else "MISS"
    # The browser must not cache this itself, or the UI would show a stale badge.
    response.headers["Cache-Control"] = "no-store"
    return StatsOut.model_validate(result.data)
