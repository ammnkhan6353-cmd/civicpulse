"""/api/complaints endpoints. HTTP concerns only - the rules live in services/."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.deps import client_ip, get_complaint_service, get_rate_limiter
from app.domain import Category, Priority, Status
from app.models import Complaint
from app.schemas import (
    ComplaintCreate,
    ComplaintOut,
    ComplaintPage,
    ErrorBody,
    StatusUpdate,
    ValidationErrorBody,
)
from app.services.complaint_service import ComplaintNotFound, ComplaintService
from app.services.rate_limiter import RateLimiter
from app.services.state_machine import InvalidTransition, allowed_next

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


def to_out(complaint: Complaint) -> ComplaintOut:
    out = ComplaintOut.model_validate(complaint)
    out.allowed_transitions = allowed_next(complaint.status)
    return out


def enforce_rate_limit(
    request: Request,
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    decision = limiter.check(client_ip(request))
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limiter.limit} complaints per minute. "
            f"Try again in {decision.retry_after_seconds} s.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ComplaintOut,
    responses={400: {"model": ValidationErrorBody}, 429: {"model": ErrorBody}},
    dependencies=[Depends(enforce_rate_limit)],
)
def create_complaint(
    payload: ComplaintCreate,
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintOut:
    return to_out(service.create(payload))


@router.get("", response_model=ComplaintPage, responses={400: {"model": ValidationErrorBody}})
def list_complaints(
    category: Category | None = None,
    priority: Priority | None = None,
    status_filter: Status | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintPage:
    items, total = service.list_page(
        category=category, priority=priority, status=status_filter, page=page, page_size=page_size
    )
    return ComplaintPage(
        items=[to_out(c) for c in items], total=total, page=page, page_size=page_size
    )


@router.get("/{complaint_id}", response_model=ComplaintOut, responses={404: {"model": ErrorBody}})
def get_complaint(
    complaint_id: uuid.UUID,
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintOut:
    try:
        return to_out(service.get(complaint_id))
    except ComplaintNotFound:
        raise HTTPException(status_code=404, detail="Complaint not found") from None


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintOut,
    responses={404: {"model": ErrorBody}, 409: {"model": ErrorBody}},
)
def update_status(
    complaint_id: uuid.UUID,
    body: StatusUpdate,
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintOut:
    try:
        return to_out(service.change_status(complaint_id, body.status))
    except ComplaintNotFound:
        raise HTTPException(status_code=404, detail="Complaint not found") from None
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
