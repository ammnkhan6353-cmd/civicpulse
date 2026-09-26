"""Retry once, with jitter, on retryable errors only.

Retryable: timeouts, connection errors, HTTP 429 and 5xx - things that may succeed
a moment later. NOT retryable: 400-class errors - the request was wrong and will be
wrong again, so retrying only burns rate-limit quota.
"""

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def call_with_retry(
    fn: Callable[[], T],
    is_retryable: Callable[[Exception], bool],
    retries: int = 1,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = lambda: random.uniform(0.2, 0.8),
) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= retries or not is_retryable(exc):
                raise
            attempt += 1
            sleep(jitter())


def is_retryable_status(status_code: int | None) -> bool:
    return status_code is not None and (status_code == 429 or status_code >= 500)
