"""Case mutation services.

:func:`transition_case` is the one write path for a case's lifecycle status. It
locks the row, checks the optimistic-concurrency ``version``, validates the move
against :mod:`app.cases.lifecycle`, applies it (managing ``closed_at`` /
``disposition``), bumps ``version`` and appends a ``case.transitioned`` event to
the case's audit stream. Like every service in this codebase it runs entirely on
the caller's session and never commits -- the route owns the transaction so the
audit write stays atomic with the state change.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit
from app.auth.deps import Principal
from app.cases.lifecycle import TransitionError, validate_transition
from app.grouping.config import get_grouping_config
from app.ingestion.service import _grouping_info, _to_alert_out
from app.models.alert import Alert
from app.models.audit import AuditEvent
from app.models.case import Case, CaseAlertLink, Note
from app.models.grouping import GroupingDecision
from app.models.user import User
from app.schemas.alert import AlertOut
from app.schemas.case import CaseDetailOut, CaseOut, NoteOut, TimelineEntry

__all__ = [
    "CaseNotFound",
    "CaseReadOnly",
    "InvalidAssignee",
    "NoteNotFound",
    "NoteRetractForbidden",
    "StaleCaseVersion",
    "add_note",
    "assign_case",
    "get_case_detail",
    "retract_note",
    "transition_case",
]


class CaseNotFound(Exception):
    """No ``cases`` row matches the requested id."""


class CaseReadOnly(Exception):
    """The case is a merge non-survivor (``status == "Merged"``) and is read-only.

    FR-OVR-01: once a case is merged into a canonical survivor it accepts no
    further notes or assignment changes -- all work continues on the survivor.
    """


class StaleCaseVersion(Exception):
    """The caller's ``expected_version`` no longer matches the persisted row."""


class InvalidAssignee(Exception):
    """The requested assignee does not exist or is not an active user."""


class NoteNotFound(Exception):
    """No ``notes`` row matches the requested id."""


class NoteRetractForbidden(Exception):
    """The actor is neither the note's author nor an admin."""


async def get_case_detail(session: AsyncSession, case_id: UUID) -> CaseDetailOut:
    """Assemble the case detail view in a bounded number of queries (no N+1).

    Four reads: the case row; its linked alerts joined to their
    :class:`GroupingDecision` (oldest ``event_time`` first); every note on the
    case (retracted included, oldest first); and the ``case:{id}`` audit stream
    (newest ``seq`` first) projected into :class:`TimelineEntry` rows. Raises
    :class:`CaseNotFound` when the id matches no row. Read-only -- never commits.
    """
    case = await session.get(Case, case_id)
    if case is None:
        raise CaseNotFound(str(case_id))
    # Server-side defaults (``updated_at``) / values mutated elsewhere in this
    # session may be unloaded or expired; load them before sync serialisation.
    await session.refresh(case)

    alert_rows = (
        await session.execute(
            select(Alert, GroupingDecision)
            .join(CaseAlertLink, CaseAlertLink.alert_id == Alert.id)
            .outerjoin(GroupingDecision, GroupingDecision.id == CaseAlertLink.grouping_decision_id)
            .where(CaseAlertLink.case_id == case_id)
            .order_by(Alert.event_time, Alert.id)
        )
    ).all()
    alerts: list[AlertOut] = []
    for alert, decision in alert_rows:
        out = _to_alert_out(alert)
        out.case_id = alert.case_id
        if decision is not None:
            out.grouping = _grouping_info(decision)
        alerts.append(out)

    notes = (
        (
            await session.execute(
                select(Note).where(Note.case_id == case_id).order_by(Note.created_at, Note.id)
            )
        )
        .scalars()
        .all()
    )

    events = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.stream == f"case:{case_id}")
                .order_by(AuditEvent.seq.desc())
            )
        )
        .scalars()
        .all()
    )
    timeline = [
        TimelineEntry(
            seq=event.seq,
            action=event.action,
            actor_id=event.actor_id,
            actor_role=event.actor_role,
            reason=event.reason,
            created_at=event.created_at,
            before=event.before,
            after=event.after,
        )
        for event in events
    ]

    return CaseDetailOut(
        **CaseOut.model_validate(case).model_dump(),
        alerts=alerts,
        notes=[NoteOut.model_validate(note) for note in notes],
        timeline=timeline,
    )


async def transition_case(
    session: AsyncSession,
    case_id: UUID,
    target: str,
    reason: str | None,
    disposition: str | None,
    actor: Principal,
    *,
    expected_version: int | None = None,
) -> Case:
    """Apply a lifecycle transition to a case and record it in the audit log.

    Steps: ``SELECT ... FOR UPDATE`` the case (:class:`CaseNotFound` if absent);
    if ``expected_version`` is given and differs, :class:`StaleCaseVersion`;
    validate the move; a ``Closed`` -> ``In Progress`` re-open with no ``reason``
    raises ``TransitionError("reopen_requires_reason")``. Then set the new status
    (``closed_at`` + ``disposition`` on close, both cleared on re-open), bump
    ``version``, and append a ``case.transitioned`` event. Never commits.
    """
    case = (
        await session.execute(select(Case).where(Case.id == case_id).with_for_update())
    ).scalar_one_or_none()
    if case is None:
        raise CaseNotFound(str(case_id))

    if expected_version is not None and expected_version != case.version:
        raise StaleCaseVersion(str(case_id))

    validate_transition(case.status, target, disposition, get_grouping_config().dispositions)

    reopening = case.status == "Closed" and target == "In Progress"
    if reopening and reason is None:
        raise TransitionError("reopen_requires_reason")

    before: dict[str, object] = {"status": case.status, "disposition": case.disposition}

    case.status = target
    if target == "Closed":
        case.disposition = disposition
        case.closed_at = datetime.now(UTC)
    elif reopening:
        case.closed_at = None
        case.disposition = None
    case.version += 1

    await record_audit(
        session,
        stream=f"case:{case.id}",
        actor=actor,
        action="case.transitioned",
        target_type="case",
        target_id=str(case.id),
        reason=reason,
        before=before,
        after={"status": case.status, "disposition": case.disposition},
    )
    return case


async def assign_case(
    session: AsyncSession,
    case_id: UUID,
    assignee_id: UUID | None,
    actor: Principal,
) -> Case:
    """(Re)assign a case, or unassign it when ``assignee_id`` is ``None``.

    ``SELECT ... FOR UPDATE`` the case (:class:`CaseNotFound` if absent). When an
    assignee is given, load the user and raise :class:`InvalidAssignee` if it
    does not exist or is inactive. Set ``assignee_id``, bump ``version``, and
    append a ``case.assigned`` audit event whose ``before`` / ``after`` carry
    only the (stringified) assignee id. Never commits.
    """
    case = (
        await session.execute(select(Case).where(Case.id == case_id).with_for_update())
    ).scalar_one_or_none()
    if case is None:
        raise CaseNotFound(str(case_id))
    if case.status == "Merged":
        raise CaseReadOnly(str(case_id))

    if assignee_id is not None:
        assignee = await session.get(User, assignee_id)
        if assignee is None or assignee.is_active is False:
            raise InvalidAssignee(str(assignee_id))

    before: dict[str, object] = {"assignee_id": str(case.assignee_id) if case.assignee_id else None}
    case.assignee_id = assignee_id
    case.version += 1
    after: dict[str, object] = {"assignee_id": str(assignee_id) if assignee_id else None}

    await record_audit(
        session,
        stream=f"case:{case.id}",
        actor=actor,
        action="case.assigned",
        target_type="case",
        target_id=str(case.id),
        before=before,
        after=after,
    )
    return case


async def add_note(
    session: AsyncSession,
    case_id: UUID,
    body: str,
    actor: Principal,
) -> Note:
    """Append an immutable note to a case's history.

    Loads the case ``FOR UPDATE`` (:class:`CaseNotFound` if absent,
    :class:`CaseReadOnly` if it is a merge non-survivor), inserts the note, and
    records a ``case.note_added`` audit event whose ``after`` holds only the note
    id and a 120-character excerpt -- the full body stays in ``notes``. Never
    commits. Callers must enforce a non-empty ``body`` (the request schema does).
    """
    case = (
        await session.execute(select(Case).where(Case.id == case_id).with_for_update())
    ).scalar_one_or_none()
    if case is None:
        raise CaseNotFound(str(case_id))
    if case.status == "Merged":
        raise CaseReadOnly(str(case_id))

    note = Note(case_id=case_id, author_id=UUID(actor.user_id), body=body)
    session.add(note)
    await session.flush()

    await record_audit(
        session,
        stream=f"case:{case_id}",
        actor=actor,
        action="case.note_added",
        target_type="note",
        target_id=str(note.id),
        after={"note_id": str(note.id), "excerpt": body[:120]},
    )
    return note


async def retract_note(
    session: AsyncSession,
    note_id: UUID,
    reason: str,
    actor: Principal,
) -> Note:
    """Retract a note -- the only permitted mutation of a :class:`Note`.

    ``SELECT ... FOR UPDATE`` the note (:class:`NoteNotFound` if absent). Authz
    lives here (not the route) so the row is loaded once: the actor must be the
    note's author or hold the ``admin`` role, else :class:`NoteRetractForbidden`.
    Retraction is idempotent -- an already-retracted note is returned unchanged
    with no second audit event. Otherwise set ``retracted`` / ``retraction_reason``
    and append a ``case.note_retracted`` event to the note's case stream. Never
    commits.
    """
    note = (
        await session.execute(select(Note).where(Note.id == note_id).with_for_update())
    ).scalar_one_or_none()
    if note is None:
        raise NoteNotFound(str(note_id))

    if actor.user_id != str(note.author_id) and "admin" not in actor.roles:
        raise NoteRetractForbidden(str(note_id))

    if note.retracted:
        return note

    note.retracted = True
    note.retraction_reason = reason

    await record_audit(
        session,
        stream=f"case:{note.case_id}",
        actor=actor,
        action="case.note_retracted",
        target_type="note",
        target_id=str(note.id),
        reason=reason,
        before={"retracted": False},
        after={"retracted": True},
    )
    return note
