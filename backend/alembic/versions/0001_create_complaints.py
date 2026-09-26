"""create complaints table with enums, check constraints and indexes

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORY = sa.Enum(
    "water", "electricity", "sanitation", "roads", "streetlights", "other",
    name="complaint_category",
)
PRIORITY = sa.Enum("high", "normal", "low", name="complaint_priority")
STATUS = sa.Enum("open", "in_progress", "resolved", "rejected", name="complaint_status")


def upgrade() -> None:
    op.create_table(
        "complaints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("reporter_contact", sa.String(200), nullable=True),
        sa.Column("category", CATEGORY, nullable=False),
        sa.Column("priority", PRIORITY, nullable=False),
        sa.Column("status", STATUS, nullable=False, server_default="open"),
        sa.Column("ai_summary", sa.String(140), nullable=True),
        sa.Column("triaged_by", sa.String(32), nullable=False),
        sa.Column("triage_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # Length rules enforced in the database as well as the app (defence in depth).
        sa.CheckConstraint("length(text) BETWEEN 10 AND 2000", name="ck_complaints_text_length"),
        sa.CheckConstraint(
            "length(location) BETWEEN 3 AND 200", name="ck_complaints_location_length"
        ),
        sa.CheckConstraint(
            "ai_summary IS NULL OR length(ai_summary) <= 140", name="ck_complaints_summary_length"
        ),
        sa.CheckConstraint(
            "triaged_by IN ('llm:groq', 'llm:ollama', 'rules', 'rules:fallback', 'simulated')",
            name="ck_complaints_triaged_by",
        ),
    )
    # Dashboard filter: WHERE status = :s AND priority = :p ORDER BY created_at DESC
    op.create_index("ix_complaints_status_priority", "complaints", ["status", "priority"])
    # Default listing: ORDER BY created_at DESC LIMIT :n OFFSET :m
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")
    op.drop_table("complaints")
    bind = op.get_bind()
    STATUS.drop(bind, checkfirst=True)
    PRIORITY.drop(bind, checkfirst=True)
    CATEGORY.drop(bind, checkfirst=True)
