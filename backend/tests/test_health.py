"""/health must never touch dependencies; /ready must name the one that failed."""

import fakeredis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.config import Settings
from app.main import create_app
from app.providers.triage.rules import RuleBasedTriage


class BrokenRedis(fakeredis.FakeRedis):
    def ping(self, **kwargs):
        raise ConnectionError("redis down")


def build(engine, redis_client):
    return create_app(
        Settings(triage_provider="rules"),
        engine=engine,
        redis_client=redis_client,
        triage_provider=RuleBasedTriage(),
    )


def test_health_ok_and_ready_ok(client):
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_ready_503_names_redis_while_health_stays_200(engine):
    with TestClient(build(engine, BrokenRedis(decode_responses=True))) as client:
        assert client.get("/health").status_code == 200
        ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["failed"] == ["redis"]


def test_ready_503_names_postgres_when_database_unreachable(tmp_path):
    missing = tmp_path / "no-such-dir" / "db.sqlite"
    broken_engine = create_engine(f"sqlite:///{missing}")
    with TestClient(build(broken_engine, fakeredis.FakeRedis(decode_responses=True))) as client:
        assert client.get("/health").status_code == 200  # liveness unaffected
        ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["failed"] == ["postgres"]


def test_metrics_exposes_prometheus_text(client):
    client.get("/health")
    body = client.get("/metrics").text
    assert "civicpulse_http_requests_total" in body
    assert "civicpulse_http_request_duration_seconds" in body
    assert "civicpulse_triage_fallback_total" in body or "civicpulse_triage_latency_ms" in body
