"""ComplaintRepository - the only module that talks SQL.

Services call these methods; routes never see a Session. Model output never
reaches SQL as text: every value is bound as a parameter by SQLAlchemy.
"""

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain import Category, Priority, Status
from app.models import Complaint


class ComplaintRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ping(self) -> None:
        self.session.execute(text("SELECT 1"))

    def add(self, complaint: Complaint) -> Complaint:
        self.session.add(complaint)
        self.session.commit()
        self.session.refresh(complaint)
        return complaint

    def get(self, complaint_id: uuid.UUID) -> Complaint | None:
        return self.session.get(Complaint, complaint_id)

    def list_page(
        self,
        *,
        category: Category | None,
        priority: Priority | None,
        status: Status | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Complaint], int]:
        filters = []
        if category is not None:
            filters.append(Complaint.category == category)
        if priority is not None:
            filters.append(Complaint.priority == priority)
        if status is not None:
            filters.append(Complaint.status == status)

        total = self.session.scalar(select(func.count()).select_from(Complaint).where(*filters))
        rows = self.session.scalars(
            select(Complaint)
            .where(*filters)
            .order_by(Complaint.created_at.desc(), Complaint.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        ).all()
        return list(rows), int(total or 0)

    def update_status(self, complaint: Complaint, new_status: Status) -> Complaint:
        complaint.status = new_status
        self.session.commit()
        self.session.refresh(complaint)
        return complaint

    def counts_by(self, column_name: str) -> dict[str, int]:
        column = getattr(Complaint, column_name)
        rows = self.session.execute(select(column, func.count()).group_by(column)).all()
        return {_enum_value(key): int(count) for key, count in rows}

    def count_all(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Complaint)) or 0)

    def insert_ignore_existing(self, rows: Iterable[dict[str, Any]]) -> int:
        """INSERT ... ON CONFLICT (id) DO NOTHING - the heart of the idempotent seed."""
        values = list(rows)
        if not values:
            return 0
        stmt: Any
        if self.session.get_bind().dialect.name == "postgresql":
            stmt = pg_insert(Complaint).values(values).on_conflict_do_nothing(index_elements=["id"])
        else:  # SQLite - used by the test suite
            stmt = sqlite_insert(Complaint).values(values).on_conflict_do_nothing(
                index_elements=["id"]
            )
        result = self.session.execute(stmt)
        self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))
