"""Unit tests for the pure case lifecycle state machine (``app.cases.lifecycle``).

No database and no app wiring: these exercise ``validate_transition`` / the
``ALLOWED`` map directly. The route- and service-level behaviour (re-open reason,
version check, audit write) is covered by ``test_case_transition.py``.
"""

from __future__ import annotations

import pytest

from app.cases.lifecycle import ALLOWED, TransitionError, validate_transition

DISP = ("No action", "Confirmed fraud")


def test_open_to_in_progress_ok() -> None:
    validate_transition("Open", "In Progress", None, DISP)


def test_open_to_closed_is_illegal() -> None:
    with pytest.raises(TransitionError, match="illegal_transition"):
        validate_transition("Open", "Closed", "No action", DISP)


def test_close_requires_disposition() -> None:
    with pytest.raises(TransitionError, match="disposition_required"):
        validate_transition("In Progress", "Closed", None, DISP)


def test_close_rejects_unknown_disposition() -> None:
    with pytest.raises(TransitionError, match="unknown_disposition"):
        validate_transition("In Progress", "Closed", "Made up", DISP)


def test_merged_is_terminal() -> None:
    with pytest.raises(TransitionError):
        validate_transition("Merged", "In Progress", None, DISP)


def test_close_with_known_disposition_ok() -> None:
    validate_transition("In Progress", "Closed", "Confirmed fraud", DISP)


def test_pending_info_back_to_in_progress_ok() -> None:
    validate_transition("Pending Info", "In Progress", None, DISP)


def test_closed_back_to_in_progress_ok() -> None:
    validate_transition("Closed", "In Progress", None, DISP)


def test_transition_error_carries_code() -> None:
    with pytest.raises(TransitionError) as excinfo:
        validate_transition("Open", "Closed", None, DISP)
    assert excinfo.value.code == "illegal_transition"


def test_allowed_map_is_exact() -> None:
    assert ALLOWED == {
        "Open": {"In Progress"},
        "In Progress": {"Pending Info", "Closed"},
        "Pending Info": {"In Progress"},
        "Closed": {"In Progress"},
        "Merged": set(),
    }
