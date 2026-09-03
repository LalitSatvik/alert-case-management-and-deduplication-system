"""The case lifecycle state machine: legal status transitions and their guards.

``ALLOWED`` is the whole graph -- ``current status -> {reachable statuses}``.
``Merged`` is terminal (a non-survivor of a merge) and has no outgoing edges;
``Closed`` can be re-opened back to ``In Progress``.

:func:`validate_transition` is pure: it checks the edge exists and, for a close,
that a disposition was supplied and is one the config knows. It does **not**
enforce the "re-open needs a reason" rule -- that depends on the request-level
``reason`` and is checked in :func:`app.cases.service.transition_case` / the
route so the failure maps to a 422 with a specific code.
"""

from __future__ import annotations

__all__ = ["ALLOWED", "TransitionError", "validate_transition"]

ALLOWED: dict[str, set[str]] = {
    "Open": {"In Progress"},
    "In Progress": {"Pending Info", "Closed"},
    "Pending Info": {"In Progress"},
    "Closed": {"In Progress"},
    "Merged": set(),
}


class TransitionError(Exception):
    """A requested status transition is not permitted.

    ``code`` is a stable, machine-readable reason -- one of ``illegal_transition``,
    ``disposition_required``, ``unknown_disposition`` or ``reopen_requires_reason``
    -- and is also the exception's message, so
    ``pytest.raises(TransitionError, match="illegal_transition")`` works.
    """

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_transition(
    current: str,
    target: str,
    disposition: str | None,
    dispositions: tuple[str, ...],
) -> None:
    """Raise :class:`TransitionError` if ``current`` -> ``target`` is not allowed.

    * ``illegal_transition`` -- ``target`` is not reachable from ``current``.
    * ``disposition_required`` -- closing without a disposition.
    * ``unknown_disposition`` -- closing with a disposition not in ``dispositions``.

    The re-open reason requirement is enforced by the caller, not here.
    """
    if target not in ALLOWED.get(current, set()):
        raise TransitionError("illegal_transition")
    if target == "Closed":
        if disposition is None:
            raise TransitionError("disposition_required")
        if disposition not in dispositions:
            raise TransitionError("unknown_disposition")
