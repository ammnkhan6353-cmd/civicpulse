# ADR 0004 — PII and data governance for LLM triage

- **Status:** Accepted
- **Date:** 2026-09-26

## Context

Citizen complaints contain personal data: names, house numbers, phone numbers, sometimes health details ("bachay beemar ho rahe hain"). Triage sends complaint text to a third party. Free LLM tiers differ in what they do with inputs — Google AI Studio's free tier states that inputs may be used to improve Google's models; Groq's free developer tier is gated by rate limits and has its own data-handling terms, which we must read rather than assume. Once data leaves our machine we cannot recall it.

## Decision

1. **Data minimisation — what leaves the machine:** only the complaint `text` and `location` are sent to the triage provider. `reporter_contact` (phone/email) is stored in our own Postgres and is **never** sent (`backend/app/providers/triage/prompt.py` builds the prompt from text and location only).
2. **Redaction before sending:** phone-number patterns (Pakistani mobile formats and long digit runs) in the text and location are replaced with `[phone redacted]` by `sanitise()` before the prompt is built.
3. **To whom:** Groq (US-hosted inference) when `TRIAGE_PROVIDER=llm`. We chose Groq over the Gemini free tier specifically to avoid a provider whose free tier trains on inputs.
4. **Zero-egress option:** `TRIAGE_PROVIDER=ollama` runs a local model in the Compose stack; nothing leaves the machine. A municipality that cannot accept any third-party processing uses this path and accepts lower classification quality and higher latency.
5. **Keys and logs:** the API key comes only from the environment (`.env` → Compose, a Kubernetes Secret, GitHub Secrets); it is a `SecretStr` and is never logged. Logs contain complaint IDs, provider names and error classes — not complaint text.
6. **Retention of derived data:** the triage cache in Redis stores only the model's output (category, priority, summary) keyed by a SHA-256 hash of the normalised text, with a 24 h TTL.

## Why this is acceptable

Complaint text is, by its nature, a report the citizen intends a public authority to act on; the location is needed for the report to be useful. Sending that minimum, with direct identifiers removed, to a processor that does not train on it is proportionate for a free-tier prototype. Residual risk: names or addresses written in free text are **not** reliably redacted by regex.

## Consequences

- Before a real deployment: sign a data-processing agreement with the provider (or move to the Ollama path), add name/address redaction (NER), and publish a privacy notice on the Submit page.
- If the provider's terms change to allow training on inputs, switching is one environment variable (ADR 0001).
