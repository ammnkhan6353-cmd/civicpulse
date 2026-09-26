"""SQLAlchemy ORM model. The schema itself is created ONLY by Alembic migrations.

This file describes the table so the repository can query it; it never creates it.
(Tests build a throwaway SQLite schema from this metadata - see tests/conftest.py.)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain import Category, Priority, Status


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint("length(text) BETWEEN 10 AND 2000", name="ck_complaints_text_length"),
        CheckConstraint(
            "length(location) BETWEEN 3 AND 200", name="ck_complaints_location_length"
        ),
        CheckConstraint(
            "ai_summary IS NULL OR length(ai_summary) <= 140", name="ck_complaints_summary_length"
        ),
        CheckConstraint(
            "triaged_by IN ('llm:groq', 'llm:ollama', 'rules', 'rules:fallback', 'simulated')",
            name="ck_complaints_triaged_by",
        ),
        # Serves the dashboard filter: WHERE status = ? AND priority = ? (see ENGINEERING-NOTES)
        Index("ix_complaints_status_priority", "status", "priority"),
        # Serves the default listing: ORDER BY created_at DESC LIMIT ? OFFSET ?
        Index("ix_complaints_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[Category] = mapped_column(
        Enum(Category, name="complaint_category"), nullable=False
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="complaint_priority"), nullable=False
    )
    status: Mapped[Status] = mapped_column(
        Enum(Status, name="complaint_status"), nullable=False, default=Status.open
    )
    ai_summary: Mapped[str | None] = mapped_column(String(140), nullable=True)
    triaged_by: Mapped[str] = mapped_column(String(32), nullable=False)
    triage_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
