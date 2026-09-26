"""Seed idempotency, triage-service caching rules, config and logging."""

import json
import logging

import fakeredis
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.logging_config import JsonFormatter, request_id_var
from app.providers.cache import CacheStore
from app.repositories.complaints import ComplaintRepository
from app.seed import run_seed
from app.seed_data import SEED_COMPLAINTS
from app.services.triage_service import TriageService
from tests.conftest import AlwaysRaises, CountingProvider


def test_seed_is_idempotent(engine):
    session = sessionmaker(bind=engine)()
    first = run_seed(session)
    second = run_seed(session)
    total = ComplaintRepository(session).count_all()
    session.close()

    assert len(SEED_COMPLAINTS) >= 30
    assert first == len(SEED_COMPLAINTS)
    assert second == 0  # running it twice changes nothing
    assert total == len(SEED_COMPLAINTS)


def test_seed_covers_every_category():
    assert {row[2] for row in SEED_COMPLAINTS} == {
        "water", "electricity", "sanitation", "roads", "streetlights", "other"
    }


def test_triage_cache_serves_duplicates_without_calling_provider():
    provider = CountingProvider()
    service = TriageService(provider, CacheStore(fakeredis.FakeRedis(decode_responses=True)), 60)
    first = service.triage("id-1", "Pipe leak near the masjid", "Lahore")
    # Different whitespace and case - same complaint, same cache entry.
    second = service.triage("id-2", "pipe  LEAK near the   masjid", "lahore")
    assert provider.calls == 1
    assert first.cache_hit is False and second.cache_hit is True
    assert second.result == first.result


def test_fallback_results_are_not_cached_and_log_one_warning(caplog):
    cache = CacheStore(fakeredis.FakeRedis(decode_responses=True))
    service = TriageService(AlwaysRaises(), cache, 60)
    with caplog.at_level(logging.WARNING, logger="civicpulse.triage"):
        decision = service.triage("complaint-42", "Water pipe burst", "Karachi")
        service.triage("complaint-43", "Water pipe burst", "Karachi")

    assert decision.triaged_by == "rules:fallback"
    assert cache.triage_lookup_counts() == (0, 2)  # the fallback was never cached
    warnings = [r for r in caplog.records if r.getMessage() == "triage fallback"]
    assert len(warnings) == 2
    assert warnings[0].complaint_id == "complaint-42"
    assert warnings[0].provider == "llm:groq"
    assert warnings[0].error_class == "TimeoutError"


def test_settings_build_postgres_url_from_parts_and_hide_password():
    settings = Settings(
        postgres_host="db", postgres_user="u", postgres_password="p", postgres_db="d"
    )
    assert settings.sqlalchemy_url() == "postgresql+psycopg://u:p@db:5432/d"
    assert "p@" not in repr(settings)  # SecretStr keeps it out of logs
    assert Settings(database_url="sqlite://").sqlalchemy_url() == "sqlite://"


def test_json_log_lines_carry_request_id():
    token = request_id_var.set("req-7")
    try:
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
        record.complaint_id = "c-1"
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["request_id"] == "req-7"
    assert line["message"] == "hello"
    assert line["complaint_id"] == "c-1"
    assert line["level"] == "INFO"
