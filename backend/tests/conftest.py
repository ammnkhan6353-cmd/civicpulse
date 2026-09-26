"""Shared fixtures. Tests are deterministic by design:

* the database is an in-memory SQLite built from the ORM metadata (test-only DDL;
  the real Postgres schema is owned by Alembic),
* Redis is fakeredis,
* the triage provider is injected - SimulatedTriage by default, or a deliberately
  broken fake when a test needs the fallback path. No network, no sleep().
"""

from collections.abc import Callable, Iterator

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.main import create_app
from app.models import Base
from app.providers.triage.base import TriageProvider, TriageResult
from app.providers.triage.simulated import SimulatedTriage

VALID = {
    "text": "Burst water main flooding Street 12 since fajr, water entering houses.",
    "location": "Street 12, G-9/2, Islamabad",
}


class AlwaysRaises:
    name = "llm:groq"

    def triage(self, text: str, location: str) -> TriageResult:
        raise TimeoutError("simulated: provider timed out")


class ReturnsMalformed:
    """Pretends to be an LLM whose output fails schema validation."""

    name = "llm:groq"

    def triage(self, text: str, location: str) -> TriageResult:
        return TriageResult.model_validate_json('{"category": "urgent", "priority": "high"}')


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.name = "simulated"
        self._inner = SimulatedTriage()

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        return self._inner.triage(text, location)


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def settings() -> Settings:
    return Settings(triage_provider="simulated", rate_limit_per_minute=1000)


@pytest.fixture
def make_app(
    engine: Engine, redis_client: fakeredis.FakeRedis, settings: Settings
) -> Callable[..., FastAPI]:
    def _make(
        provider: TriageProvider | None = None, app_settings: Settings | None = None
    ) -> FastAPI:
        return create_app(
            app_settings or settings,
            engine=engine,
            redis_client=redis_client,
            triage_provider=provider or SimulatedTriage(),
        )

    return _make


@pytest.fixture
def client(make_app: Callable[..., FastAPI]) -> Iterator[TestClient]:
    with TestClient(make_app()) as test_client:
        yield test_client
