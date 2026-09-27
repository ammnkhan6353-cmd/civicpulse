"""Complaint status state machine - an explicit transition table, not a chain of ifs.

    open ──► in_progress ──► resolved
      │           │
      └──► rejected ◄──┘          resolved and rejected are terminal.
"""

from app.domain import Status

TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.open: frozenset({Status.in_progress, Status.rejected}),
    Status.in_progress: frozenset({Status.resolved, Status.rejected}),
    Status.resolved: frozenset(),
    Status.rejected: frozenset(),
}


class InvalidTransition(Exception):
    def __init__(self, current: Status, requested: Status) -> None:
        self.current = current
        self.requested = requested
        super().__init__(f"Invalid transition: {current.value} → {requested.value}")


def allowed_next(current: Status) -> list[Status]:
    # Sorted so the API response (and the UI buttons) have a stable order.
    return sorted(TRANSITIONS[current], key=lambda s: list(Status).index(s))


def assert_transition(current: Status, requested: Status) -> None:
    if requested not in TRANSITIONS[current]:
        raise InvalidTransition(current, requested)
