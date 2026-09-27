"""The TriageProvider contract (ADR 0001).

Every provider - hosted LLM, local Ollama, keyword rules, CI fake - takes the
complaint text and location and returns a TriageResult. The rest of the system
depends only on this file, so the reader is replaceable.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain import Category, Priority


class TriageResult(BaseModel):
    # extra="forbid": a model that invents extra keys is not following the schema.
    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority
    summary: str = Field(min_length=1, max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)


class TriageProvider(Protocol):
    name: str

    def triage(self, text: str, location: str) -> TriageResult: ...


class TriageError(Exception):
    """Raised by a provider when it cannot produce a valid TriageResult."""


class MalformedTriageOutput(TriageError):
    """The provider answered, but the answer failed schema validation."""
