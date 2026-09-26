"""Integration tests for the HTTP contract (all ten endpoints)."""

import uuid

from fastapi.testclient import TestClient

from app.config import Settings
from app.services import rate_limiter
from tests.conftest import VALID


def create(client: TestClient, **overrides) -> dict:
    response = client.post("/api/complaints", json={**VALID, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_post_complaint_returns_201_with_triage_fields(client):
    body = create(client, reporter_contact="0300-1234567")
    assert body["category"] == "water"
    assert body["priority"] == "high"
    assert body["status"] == "open"
    assert body["triaged_by"] == "simulated"
    assert body["ai_summary"] and len(body["ai_summary"]) <= 140
    assert isinstance(body["triage_latency_ms"], int)
    assert body["allowed_transitions"] == ["in_progress", "rejected"]


def test_post_invalid_body_returns_400_with_field_level_errors(client):
    response = client.post("/api/complaints", json={"text": "short", "location": "x"})
    assert response.status_code == 400
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields == {"text", "location"}


def test_get_complaint_by_id_and_404(client):
    created = create(client)
    assert client.get(f"/api/complaints/{created['id']}").json()["id"] == created["id"]
    assert client.get(f"/api/complaints/{uuid.uuid4()}").status_code == 404


def test_list_filters_and_paginates(client):
    create(client)
    create(client, text="Street lights not working for two weeks, very dark at night here.")
    create(client, text="Garbage not collected for a week, bad smell in the whole street.")

    everything = client.get("/api/complaints", params={"page_size": 2}).json()
    assert everything["total"] == 3
    assert len(everything["items"]) == 2
    assert everything["page"] == 1

    page_two = client.get("/api/complaints", params={"page_size": 2, "page": 2}).json()
    assert len(page_two["items"]) == 1

    lights = client.get("/api/complaints", params={"category": "streetlights"}).json()
    assert lights["total"] == 1
    assert lights["items"][0]["category"] == "streetlights"


def test_page_size_above_100_is_rejected(client):
    response = client.get("/api/complaints", params={"page_size": 101})
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "page_size"


def test_valid_status_transition_then_invalid_returns_409_naming_it(client):
    created = create(client)
    url = f"/api/complaints/{created['id']}/status"

    moved = client.patch(url, json={"status": "in_progress"})
    assert moved.status_code == 200
    assert moved.json()["allowed_transitions"] == ["resolved", "rejected"]

    assert client.patch(url, json={"status": "resolved"}).status_code == 200
    conflict = client.patch(url, json={"status": "open"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Invalid transition: resolved → open"


def test_patch_unknown_complaint_is_404(client):
    response = client.patch(f"/api/complaints/{uuid.uuid4()}/status", json={"status": "resolved"})
    assert response.status_code == 404


def test_stats_cache_miss_then_hit_then_invalidated_by_write(client):
    create(client)
    first = client.get("/api/stats")
    second = client.get("/api/stats")
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert second.json()["total"] == 1
    assert second.json()["by_category"]["water"] == 1

    create(client)  # a write must invalidate, not wait 30 s for the TTL
    third = client.get("/api/stats")
    assert third.headers["X-Cache"] == "MISS"
    assert third.json()["total"] == 2


def test_status_change_also_invalidates_stats(client):
    created = create(client)
    client.get("/api/stats")
    client.patch(f"/api/complaints/{created['id']}/status", json={"status": "rejected"})
    after = client.get("/api/stats")
    assert after.headers["X-Cache"] == "MISS"
    assert after.json()["by_status"]["rejected"] == 1


def test_rate_limit_returns_429_with_retry_after(make_app, monkeypatch):
    # Freeze the clock 20 s into a window so the test can never straddle a minute boundary.
    monkeypatch.setattr(rate_limiter.time, "time", lambda: 1_800_000_020.0)
    app = make_app(app_settings=Settings(triage_provider="simulated", rate_limit_per_minute=2))
    with TestClient(app) as client:
        headers = {"X-Forwarded-For": "203.0.113.7"}
        for _ in range(2):
            assert client.post("/api/complaints", json=VALID, headers=headers).status_code == 201
        blocked = client.post("/api/complaints", json=VALID, headers=headers)
        # A different client IP is not affected by someone else's limit.
        other_ip = {"X-Forwarded-For": "198.51.100.1"}
        other = client.post("/api/complaints", json=VALID, headers=other_ip)

    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "40"
    assert other.status_code == 201


def test_duplicate_complaint_is_served_from_triage_cache(client):
    create(client)
    create(client)
    meta = client.get("/api/meta/providers").json()
    assert meta["triage_cache"]["hits"] == 1
    assert meta["triage_cache"]["misses"] == 1
    assert meta["triage_cache"]["hit_rate"] == 0.5
    assert meta["recent"][0]["cache_hit"] is True
    assert "latency_ms" in meta["recent"][0]


def test_request_id_is_propagated(client):
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) == 32
