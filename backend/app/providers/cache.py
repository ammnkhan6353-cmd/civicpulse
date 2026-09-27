"""Redis access. Redis does two jobs in CivicPulse:

1. Cache  - /api/stats read-through cache and the triage content-hash cache.
2. Limiter - the distributed fixed-window rate limiter on POST /api/complaints.

Every Redis command the app issues lives in this module, so services depend on a
small, testable interface instead of on the redis client directly.
"""

import json
from typing import Any, Protocol

import redis

STATS_KEY = "stats:v1"
TRIAGE_PREFIX = "triage:"
TRIAGE_HITS = "triage:meta:hits"
TRIAGE_MISSES = "triage:meta:misses"
TRIAGE_OUTCOMES = "triage:meta:outcomes"


class RedisLike(Protocol):
    def get(self, name: str) -> Any: ...
    def set(self, name: str, value: Any, ex: int | None = None) -> Any: ...
    def delete(self, *names: str) -> Any: ...
    def incr(self, name: str, amount: int = 1) -> Any: ...
    def expire(self, name: str, time: int) -> Any: ...
    def lpush(self, name: str, *values: Any) -> Any: ...
    def ltrim(self, name: str, start: int, end: int) -> Any: ...
    def lrange(self, name: str, start: int, end: int) -> Any: ...
    def ping(self) -> Any: ...


def build_redis(url: str) -> "redis.Redis":
    # Short timeouts: a slow Redis must degrade us, not hang every request.
    return redis.Redis.from_url(
        url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
    )


class CacheStore:
    def __init__(self, client: RedisLike) -> None:
        self.client = client

    # --- generic JSON get/set -------------------------------------------------
    def get_json(self, key: str) -> Any | None:
        raw = self.client.get(key)
        return json.loads(raw) if raw is not None else None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.client.set(key, json.dumps(value), ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def ping(self) -> bool:
        return bool(self.client.ping())

    # --- triage cache bookkeeping ---------------------------------------------
    def record_triage_lookup(self, hit: bool) -> None:
        self.client.incr(TRIAGE_HITS if hit else TRIAGE_MISSES)

    def triage_lookup_counts(self) -> tuple[int, int]:
        hits = int(self.client.get(TRIAGE_HITS) or 0)
        misses = int(self.client.get(TRIAGE_MISSES) or 0)
        return hits, misses

    def push_outcome(self, outcome: dict[str, Any], keep: int = 20) -> None:
        self.client.lpush(TRIAGE_OUTCOMES, json.dumps(outcome))
        self.client.ltrim(TRIAGE_OUTCOMES, 0, keep - 1)

    def recent_outcomes(self, keep: int = 20) -> list[dict[str, Any]]:
        return [json.loads(item) for item in self.client.lrange(TRIAGE_OUTCOMES, 0, keep - 1)]

    # --- rate limiter -----------------------------------------------------------
    def incr_window(self, key: str, window_seconds: int) -> int:
        count = int(self.client.incr(key))
        if count == 1:
            # First hit in this window: make the key expire with the window.
            self.client.expire(key, window_seconds)
        return count
