"""Prometheus metrics exposed at GET /metrics."""

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "civicpulse_http_requests_total",
    "HTTP requests served",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "civicpulse_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)
TRIAGE_LATENCY = Histogram(
    "civicpulse_triage_latency_ms",
    "Triage latency in milliseconds (cache hits excluded)",
    ["provider"],
    buckets=(5, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000, 20000),
)
TRIAGE_FALLBACK = Counter(
    "civicpulse_triage_fallback_total",
    "Triage calls that fell back to RuleBasedTriage",
    ["provider", "error_class"],
)
TRIAGE_CACHE = Counter(
    "civicpulse_triage_cache_total",
    "Triage content-hash cache lookups",
    ["result"],  # hit | miss
)
