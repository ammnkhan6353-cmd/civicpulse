"""SimulatedTriage - deterministic fake for CI. No network, seeded, failure-injectable.

Same input -> same output on every run, so CI is green on every single run.
SIMULATED_FAILURE_MODE lets the integration environment exercise the fallback path:
  none      - behave normally
  raise     - raise a TriageError (simulates timeout / 429 / outage)
  malformed - return output that fails schema validation
"""

import hashlib

from pydantic import ValidationError

from app.providers.triage.base import MalformedTriageOutput, TriageError, TriageResult
from app.providers.triage.rules import RuleBasedTriage


class SimulatedTriage:
    name = "simulated"

    def __init__(self, failure_mode: str = "none") -> None:
        self.failure_mode = failure_mode
        self._rules = RuleBasedTriage()

    def triage(self, text: str, location: str) -> TriageResult:
        if self.failure_mode == "raise":
            raise TriageError("simulated provider failure")
        if self.failure_mode == "malformed":
            try:
                # A plausible-looking but invalid answer: category outside the enum.
                return TriageResult.model_validate(
                    {"category": "urgent", "priority": "high", "summary": "x", "confidence": 2}
                )
            except ValidationError as exc:
                raise MalformedTriageOutput(str(exc)) from exc

        base = self._rules.triage(text, location)
        # Deterministic "model confidence" derived from a hash of the input.
        digest = hashlib.sha256(f"{text}|{location}".encode()).digest()
        confidence = round(0.6 + (digest[0] / 255) * 0.35, 2)
        summary = f"[sim] {base.summary}"
        if len(summary) > 140:
            summary = summary[:137].rstrip() + "..."
        return TriageResult(
            category=base.category,
            priority=base.priority,
            summary=summary,
            confidence=confidence,
        )
