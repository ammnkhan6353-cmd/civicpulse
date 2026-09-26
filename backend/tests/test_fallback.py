"""The test the assignment says to write if you write no other:
given a provider that always raises, POST /api/complaints still returns 201
and triaged_by == "rules:fallback"."""

from fastapi.testclient import TestClient

from tests.conftest import VALID, AlwaysRaises, ReturnsMalformed


def test_provider_that_always_raises_still_returns_201_with_rules_fallback(make_app):
    with TestClient(make_app(AlwaysRaises())) as client:
        response = client.post("/api/complaints", json=VALID)

    assert response.status_code == 201
    body = response.json()
    assert body["triaged_by"] == "rules:fallback"
    assert body["category"] == "water"  # the rules still classify it sensibly
    assert body["priority"] == "high"


def test_malformed_provider_output_is_rejected_and_falls_back(make_app):
    with TestClient(make_app(ReturnsMalformed())) as client:
        response = client.post("/api/complaints", json=VALID)

    assert response.status_code == 201
    assert response.json()["triaged_by"] == "rules:fallback"


def test_fallback_is_visible_in_meta_providers(make_app):
    with TestClient(make_app(AlwaysRaises())) as client:
        created = client.post("/api/complaints", json=VALID).json()
        meta = client.get("/api/meta/providers").json()

    latest = meta["recent"][0]
    assert latest["complaint_id"] == created["id"]
    assert latest["fallback"] is True
    assert latest["provider"] == "rules:fallback"
    assert meta["active_provider"] == "llm:groq"
