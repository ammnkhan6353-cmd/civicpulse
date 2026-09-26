import pytest

from app.domain import Status
from app.services.state_machine import InvalidTransition, allowed_next, assert_transition


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        (Status.open, Status.in_progress),
        (Status.open, Status.rejected),
        (Status.in_progress, Status.resolved),
        (Status.in_progress, Status.rejected),
    ],
)
def test_allowed_transitions(current, requested):
    assert_transition(current, requested)  # does not raise


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        (Status.open, Status.resolved),  # must pass through in_progress
        (Status.in_progress, Status.open),  # no going back
        (Status.resolved, Status.open),  # terminal
        (Status.rejected, Status.in_progress),  # terminal
        (Status.open, Status.open),  # self-transition is not a transition
    ],
)
def test_invalid_transitions_raise_with_readable_message(current, requested):
    with pytest.raises(InvalidTransition) as info:
        assert_transition(current, requested)
    assert str(info.value) == f"Invalid transition: {current.value} → {requested.value}"


def test_terminal_states_allow_nothing():
    assert allowed_next(Status.resolved) == []
    assert allowed_next(Status.rejected) == []
    assert allowed_next(Status.open) == [Status.in_progress, Status.rejected]
