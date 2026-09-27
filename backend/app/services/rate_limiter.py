"""Distributed fixed-window rate limiter backed by Redis.

It MUST live in Redis, not in a Python dict: when the HPA scales the backend to
four pods, an in-process limiter would allow four times the traffic, and our
free LLM tier (tens of requests per minute) would be exhausted by one for-loop.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.providers.cache import CacheStore

logger = logging.getLogger("civicpulse.ratelimit")

WINDOW_SECONDS = 60


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int
    count: int


class RateLimiter:
    def __init__(
        self,
        cache: CacheStore,
        limit_per_minute: int,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.cache = cache
        self.limit = limit_per_minute
        self.clock = clock or time.time

    def check(self, client_ip: str) -> RateLimitDecision:
        now = self.clock()
        window = int(now // WINDOW_SECONDS)
        key = f"ratelimit:{client_ip}:{window}"
        try:
            count = self.cache.incr_window(key, WINDOW_SECONDS)
        except Exception:  # noqa: BLE001
            # Fail open: if Redis is down /ready already reports it; refusing every
            # citizen complaint would be worse than briefly not rate limiting.
            logger.warning("rate limiter unavailable; allowing request", exc_info=True)
            return RateLimitDecision(True, 0, 0)
        retry_after = max(1, WINDOW_SECONDS - int(now % WINDOW_SECONDS))
        return RateLimitDecision(count <= self.limit, retry_after, count)
