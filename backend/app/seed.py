"""Idempotent seed:  python -m app.seed

Idempotency by design, not by luck:
  * every seed row gets a DETERMINISTIC id: uuid5(namespace, text)
  * rows are inserted with INSERT ... ON CONFLICT (id) DO NOTHING
Running it twice (or on every container start) never duplicates a row.
Seed rows are triaged by the rules provider - no LLM quota is spent on seeding.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import build_engine, build_session_factory
from app.domain import Category, Priority, Status
from app.logging_config import configure_logging
from app.repositories.complaints import ComplaintRepository
from app.seed_data import SEED_COMPLAINTS

SEED_NAMESPACE = uuid.UUID("6f1c2a9e-3c1b-4d7e-9a55-1c3f0e2b7d10")
logger = logging.getLogger("civicpulse.seed")


def seed_rows() -> list[dict[str, Any]]:
    base_time = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    rows = []
    for index, (text, location, category, priority, status) in enumerate(SEED_COMPLAINTS):
        summary = " ".join(text.split())
        if len(summary) > 140:
            summary = summary[:137].rstrip() + "..."
        created = base_time + timedelta(hours=7 * index)
        rows.append(
            {
                "id": uuid.uuid5(SEED_NAMESPACE, text),
                "text": text,
                "location": location,
                "reporter_contact": None,
                "category": Category(category),
                "priority": Priority(priority),
                "status": Status(status),
                "ai_summary": summary,
                "triaged_by": "rules",
                "triage_latency_ms": 0,
                "created_at": created,
                "updated_at": created,
            }
        )
    return rows


def run_seed(session: Session) -> int:
    inserted = ComplaintRepository(session).insert_ignore_existing(seed_rows())
    logger.info("seed complete", extra={"inserted": inserted, "seed_size": len(SEED_COMPLAINTS)})
    return inserted


def main() -> None:  # pragma: no cover - thin CLI wrapper
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.sqlalchemy_url())
    session = build_session_factory(engine)()
    try:
        run_seed(session)
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    main()
