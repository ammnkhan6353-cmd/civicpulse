# ADR 0001 — Triage behind a `TriageProvider` interface

- **Status:** Accepted
- **Date:** 2026-09-26

## Context

Complaint triage (category, priority, one-line summary) is the core of CivicPulse, and the thing doing it will change: a keyword rule today, a hosted LLM now, perhaps a local or fine-tuned model later. Hosted free-tier LLMs are also unreliable in ways we do not control — rate limits (429), timeouts, outages, and output that is plausible but wrong (prose, code fences, categories outside our enum, over-long summaries). CI must be deterministic even though an LLM is not.

## Decision

All triage goes through one interface in `backend/app/providers/triage/base.py`:

```python
class TriageResult(BaseModel):          # extra keys forbidden
    category: Category                  # enum
    priority: Priority                  # enum
    summary: str = Field(max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)

class TriageProvider(Protocol):
    name: str
    def triage(self, text: str, location: str) -> TriageResult: ...
```

Four implementations, chosen by the `TRIAGE_PROVIDER` environment variable in `factory.py`:

| `TRIAGE_PROVIDER` | Class | `triaged_by` | Use |
|---|---|---|---|
| `llm` (default) | `LLMTriage` | `llm:groq` | Production. Groq free tier via the OpenAI-compatible SDK, JSON mode |
| `ollama` | `OllamaTriage` | `llm:ollama` | Fully offline, a container in the Compose stack |
| `rules` | `RuleBasedTriage` | `rules` | Deterministic keywords; never raises |
| `simulated` | `SimulatedTriage` | `simulated` | CI fake: seeded, no network, `SIMULATED_FAILURE_MODE=raise\|malformed` |

The orchestration around the provider lives in `services/triage_service.py`, **not** in any provider: content-hash cache lookup → provider call → on *any* exception, `RuleBasedTriage` with `triaged_by = "rules:fallback"` plus one WARNING log line and a metric → record the outcome for `/api/meta/providers`. Each LLM provider validates its own output against `TriageResult` and owns its timeout (10 s) and retry policy (one jittered retry on timeout/connection error/429/5xx, never on 400).

We use a `typing.Protocol` (structural typing) rather than an abstract base class so a provider does not need to import or inherit anything from our code — a test double is just a class with `name` and `triage()`.

## Consequences

- Adding a provider (Gemini, a fine-tuned classifier) is one new file plus one line in the factory; routes, services, database and frontend do not change.
- The Pydantic model is the single source of truth for "valid triage": HTTP input and LLM output are validated by the same machinery.
- CI pins `TRIAGE_PROVIDER=simulated` and tests inject deliberately broken providers, so the fallback path is tested on every run without network or `sleep()`.
- We added `simulated` to the allowed `triaged_by` values (DB check constraint) so rows written by the fake are labelled honestly rather than pretending to be `rules`.
- Trade-off: the fallback hides provider failures from citizens, so failures must be made visible elsewhere — the WARNING log, `civicpulse_triage_fallback_total`, and `/api/meta/providers` (see RUNBOOK "triage starts failing").
