"""Aggregate statistics with a Redis read-through cache (TTL 30 s + invalidate on write).

Why both? Invalidation gives freshness: a new complaint appears immediately.
The TTL is the safety net: if an invalidation is ever missed (a write from another
tool, a failed DELETE, a future code path that forgets to call invalidate()),
stale data still heals itself within 30 seconds.
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.domain import Category, Priority, Status
from app.providers.cache import STATS_KEY, CacheStore
from app.repositories.complaints import ComplaintRepository

logger = logging.getLogger("civicpulse.stats")


@dataclass(frozen=True)
class StatsResult:
    data: dict[str, Any]
    cache_hit: bool


class StatsService:
    def __init__(
        self, repository: ComplaintRepository, cache: CacheStore, ttl_seconds: int
    ) -> None:
        self.repository = repository
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    def get(self) -> StatsResult:
        try:
            cached = self.cache.get_json(STATS_KEY)
        except Exception:  # noqa: BLE001 - a cache outage must not break the endpoint
            logger.warning("stats cache read failed", exc_info=True)
            cached = None
        if cached is not None:
            return StatsResult(cached, cache_hit=True)

        data = self._compute()
        try:
            self.cache.set_json(STATS_KEY, data, self.ttl_seconds)
        except Exception:  # noqa: BLE001
            logger.warning("stats cache write failed", exc_info=True)
        return StatsResult(data, cache_hit=False)

    def invalidate(self) -> None:
        try:
            self.cache.delete(STATS_KEY)
        except Exception:  # noqa: BLE001
            logger.warning("stats cache invalidation failed; TTL will heal it", exc_info=True)

    def _compute(self) -> dict[str, Any]:
        def with_zeros(counts: dict[str, int], values: list[str]) -> dict[str, int]:
            return {value: counts.get(value, 0) for value in values}

        return {
            "total": self.repository.count_all(),
            "by_category": with_zeros(
                self.repository.counts_by("category"), [c.value for c in Category]
            ),
            "by_priority": with_zeros(
                self.repository.counts_by("priority"), [p.value for p in Priority]
            ),
            "by_status": with_zeros(
                self.repository.counts_by("status"), [s.value for s in Status]
            ),
        }
