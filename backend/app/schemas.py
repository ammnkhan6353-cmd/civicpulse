"""HTTP request/response models. These generate the OpenAPI schema that the
frontend's TypeScript client is generated from (frontend/src/api/schema.d.ts)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import Category, Priority, Status


class ComplaintCreate(BaseModel):
    text: str = Field(min_length=10, max_length=2000, description="Free-text complaint")
    location: str = Field(min_length=3, max_length=200)
    reporter_contact: str | None = Field(default=None, max_length=200)

    @field_validator("text", "location")
    @classmethod
    def strip_and_require(cls, value: str) -> str:
        return value.strip()

    @field_validator("reporter_contact")
    @classmethod
    def empty_contact_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    status: Status
    ai_summary: str | None
    triaged_by: str
    triage_latency_ms: int
    created_at: datetime
    updated_at: datetime
    allowed_transitions: list[Status] = Field(
        default_factory=list,
        description="Statuses the backend will accept next. Computed by the state machine.",
    )


class ComplaintPage(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class StatusUpdate(BaseModel):
    status: Status


class StatsOut(BaseModel):
    total: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]


class TriageOutcome(BaseModel):
    complaint_id: str
    provider: str
    latency_ms: int
    fallback: bool
    cache_hit: bool
    at: str


class CacheStats(BaseModel):
    hits: int
    misses: int
    hit_rate: float


class ProvidersOut(BaseModel):
    active_provider: str
    fallback_provider: str
    available_providers: list[str]
    triage_cache: CacheStats
    recent: list[TriageOutcome]


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorBody(BaseModel):
    detail: str
    errors: list[FieldError]


class ErrorBody(BaseModel):
    detail: str
