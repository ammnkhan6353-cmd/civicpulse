"""ComplaintService - validate -> triage -> persist, and the status state machine."""

import uuid

from app.domain import Category, Priority, Status
from app.models import Complaint
from app.repositories.complaints import ComplaintRepository
from app.schemas import ComplaintCreate
from app.services.state_machine import assert_transition
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


class ComplaintNotFound(Exception):
    pass


class ComplaintService:
    def __init__(
        self,
        repository: ComplaintRepository,
        triage: TriageService,
        stats: StatsService,
    ) -> None:
        self.repository = repository
        self.triage = triage
        self.stats = stats

    def create(self, payload: ComplaintCreate) -> Complaint:
        complaint_id = uuid.uuid4()
        decision = self.triage.triage(str(complaint_id), payload.text, payload.location)
        complaint = Complaint(
            id=complaint_id,
            text=payload.text,
            location=payload.location,
            reporter_contact=payload.reporter_contact,
            category=decision.result.category,
            priority=decision.result.priority,
            status=Status.open,
            ai_summary=decision.result.summary,
            triaged_by=decision.triaged_by,
            triage_latency_ms=decision.latency_ms,
        )
        saved = self.repository.add(complaint)
        # Invalidate on write so the new complaint shows up in stats immediately.
        self.stats.invalidate()
        return saved

    def get(self, complaint_id: uuid.UUID) -> Complaint:
        complaint = self.repository.get(complaint_id)
        if complaint is None:
            raise ComplaintNotFound(str(complaint_id))
        return complaint

    def list_page(
        self,
        *,
        category: Category | None,
        priority: Priority | None,
        status: Status | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Complaint], int]:
        return self.repository.list_page(
            category=category, priority=priority, status=status, page=page, page_size=page_size
        )

    def change_status(self, complaint_id: uuid.UUID, new_status: Status) -> Complaint:
        complaint = self.get(complaint_id)
        assert_transition(complaint.status, new_status)  # raises InvalidTransition -> 409
        updated = self.repository.update_status(complaint, new_status)
        self.stats.invalidate()
        return updated
