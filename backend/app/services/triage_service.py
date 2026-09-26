"""Triage orchestration: content-hash cache -> provider -> fallback -> record outcome.

A citizen must never see a 500 because a third party was slow, rate-limited or
wrong: any provider failure falls back to RuleBasedTriage with
triaged_by = "rules:fallback", one WARNING log line and a metric increment.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from app.metrics import TRIAGE_CACHE, TRIAGE_FALLBACK, TRIAGE_LATENCY
from app.providers.cache import TRIAGE_PREFIX, CacheStore
from app.providers.triage.base import TriageProvider, TriageResult
from app.providers.triage.rules import RuleBasedTriage

logger = logging.getLogger("civicpulse.triage")

FALLBACK_NAME = "rules:fallback"


@dataclass(frozen=True)
class TriageDecision:
    result: TriageResult
    triaged_by: str
    latency_ms: int
    cache_hit: bool

    @property
    def fallback(self) -> bool:
        return self.triaged_by == FALLBACK_NAME


def content_hash(text: str, location: str) -> str:
    """Normalise so trivially different duplicates share one cache entry."""
    normalised = " ".join(f"{text}|{location}".lower().split())
    return hashlib.sha256(normalised.encode()).hexdigest()


class TriageService:
    def __init__(
        self,
        provider: TriageProvider,
        cache: CacheStore,
        cache_ttl_seconds: int,
        fallback: TriageProvider | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.cache_ttl_seconds = cache_ttl_seconds
        self.fallback = fallback or RuleBasedTriage()

    def triage(self, complaint_id: str, text: str, location: str) -> TriageDecision:
        key = TRIAGE_PREFIX + content_hash(text, location)
        start = time.perf_counter()

        cached = self._cache_get(key)
        if cached is not None:
            decision = TriageDecision(
                result=TriageResult.model_validate(cached["result"]),
                triaged_by=cached["triaged_by"],
                latency_ms=int((time.perf_counter() - start) * 1000),
                cache_hit=True,
            )
            self._record(complaint_id, decision)
            return decision

        try:
            result = self.provider.triage(text, location)
            triaged_by = self.provider.name
        except Exception as exc:  # noqa: BLE001 - ANY provider failure must fall back
            logger.warning(
                "triage fallback",
                extra={
                    "complaint_id": complaint_id,
                    "provider": self.provider.name,
                    "error_class": type(exc).__name__,
                },
            )
            TRIAGE_FALLBACK.labels(self.provider.name, type(exc).__name__).inc()
            result = self.fallback.triage(text, location)
            triaged_by = FALLBACK_NAME

        latency_ms = int((time.perf_counter() - start) * 1000)
        TRIAGE_LATENCY.labels(triaged_by).observe(latency_ms)
        decision = TriageDecision(result, triaged_by, latency_ms, cache_hit=False)

        # Only cache real provider answers. Caching a fallback would pin the
        # rules answer for 24 h even after the LLM recovers.
        if not decision.fallback:
            self._cache_set(key, decision)
        self._record(complaint_id, decision)
        return decision

    # --- cache helpers: Redis trouble degrades caching, never the request -------
    def _cache_get(self, key: str) -> dict | None:
        try:
            cached = self.cache.get_json(key)
            self.cache.record_triage_lookup(hit=cached is not None)
        except Exception:  # noqa: BLE001
            logger.warning("triage cache unavailable", exc_info=True)
            return None
        TRIAGE_CACHE.labels("hit" if cached is not None else "miss").inc()
        return cached

    def _cache_set(self, key: str, decision: TriageDecision) -> None:
        try:
            payload = {
                "result": decision.result.model_dump(mode="json"),
                "triaged_by": decision.triaged_by,
            }
            self.cache.set_json(key, payload, self.cache_ttl_seconds)
        except Exception:  # noqa: BLE001
            logger.warning("triage cache write failed", exc_info=True)

    def _record(self, complaint_id: str, decision: TriageDecision) -> None:
        try:
            self.cache.push_outcome(
                {
                    "complaint_id": complaint_id,
                    "provider": decision.triaged_by,
                    "latency_ms": decision.latency_ms,
                    "fallback": decision.fallback,
                    "cache_hit": decision.cache_hit,
                    "at": datetime.now(UTC).isoformat(),
                }
            )
        except Exception:  # noqa: BLE001
            logger.warning("could not record triage outcome", exc_info=True)
