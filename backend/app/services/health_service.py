"""Readiness checks: is every dependency this pod needs reachable?"""

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.providers.cache import CacheStore
from app.repositories.complaints import ComplaintRepository

logger = logging.getLogger("civicpulse.health")


class HealthService:
    def __init__(self, session_factory: Callable[[], Session], cache: CacheStore) -> None:
        self.session_factory = session_factory
        self.cache = cache

    def failed_dependencies(self) -> list[str]:
        failed: list[str] = []
        session = self.session_factory()
        try:
            ComplaintRepository(session).ping()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "readiness: postgres unreachable", extra={"error_class": type(exc).__name__}
            )
            failed.append("postgres")
        finally:
            session.close()

        try:
            self.cache.ping()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "readiness: redis unreachable", extra={"error_class": type(exc).__name__}
            )
            failed.append("redis")
        return failed
