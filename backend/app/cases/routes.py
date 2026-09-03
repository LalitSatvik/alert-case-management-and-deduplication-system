"""``/api/v1/cases`` endpoints.

The lifecycle transition endpoint:
``POST /api/v1/cases/{case_id}/transition`` (roles: analyst, admin). The body is
:class:`~app.schemas.case.TransitionRequest`; an optional ``If-Match`` header
carries the case ``version`` the caller last saw for optimistic concurrency.

Exception -> status mapping:

* :class:`~app.cases.service.CaseNotFound`     -> ``404``
* :class:`~app.cases.service.StaleCaseVersion` -> ``409``
* :class:`~app.cases.lifecycle.TransitionError` with ``code == "illegal_transition"`` -> ``409``
* any other :class:`~app.cases.lifecycle.TransitionError` code -> ``422``

On success the transaction is committed and the updated case is returned (``200``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal, get_current_principal, require_role
from app.cases.lifecycle import TransitionError
from app.cases.search import CaseFilters, InvalidCursor, case_stats, paginate
from app.cases.service import (
    CaseNotFound,
    CaseReadOnly,
    InvalidAssignee,
    NoteNotFound,
    NoteRetractForbidden,
    StaleCaseVersion,
    add_note,
    assign_case,
    get_case_detail,
    retract_note,
    transition_case,
)
from app.db import get_session
from app.models.case import Note
from app.schemas.case import (
    AssignRequest,
    CaseDetailOut,
    CaseListPage,
    CaseOut,
    CaseStatsOut,
    NoteCreate,
    NoteOut,
    NoteRetract,
    TransitionRequest,
)

router = APIRouter(prefix="/cases", tags=["cases"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_READ_ROLES = require_role("analyst", "admin", "readonly")


def _case_filters(
    status_in: Annotated[list[str], Query(alias="status", default_factory=list)],
    disposition: Annotated[list[str], Query(default_factory=list)],
    assignee_id: Annotated[str | None, Query()] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
    closed_from: Annotated[datetime | None, Query()] = None,
    closed_to: Annotated[datetime | None, Query()] = None,
    risk_min: Annotated[int | None, Query(ge=0, le=100)] = None,
    risk_max: Annotated[int | None, Query(ge=0, le=100)] = None,
    source_system: Annotated[str | None, Query()] = None,
    typology: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    sort: Annotated[Literal["-risk_score", "-created_at", "oldest_alert"], Query()] = "-risk_score",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> CaseFilters:
    """Map the ``GET /cases`` query string to a :class:`CaseFilters`.

    ``assignee_id`` accepts the literal ``unassigned`` (-> ``IS NULL``) or a UUID;
    anything else is a 422.
    """
    assignee: UUID | Literal["unassigned"] | None
    if assignee_id in (None, ""):
        assignee = None
    elif assignee_id == "unassigned":
        assignee = "unassigned"
    else:
        try:
            assignee = UUID(assignee_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="invalid_assignee_id",
            ) from exc
    return CaseFilters(
        status=status_in,
        disposition=disposition,
        assignee_id=assignee,
        created_from=created_from,
        created_to=created_to,
        closed_from=closed_from,
        closed_to=closed_to,
        risk_min=risk_min,
        risk_max=risk_max,
        source_system=source_system,
        typology=typology,
        q=q,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )


@router.get("", response_model=CaseListPage, dependencies=[Depends(_READ_ROLES)])
async def list_cases(
    session: SessionDep,
    filters: Annotated[CaseFilters, Depends(_case_filters)],
) -> CaseListPage:
    """Filtered, keyset-paginated case list. Read-only; ``readonly`` role allowed."""
    try:
        items, next_cursor = await paginate(session, filters)
    except InvalidCursor as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from exc
    return CaseListPage(items=items, next_cursor=next_cursor)


@router.get("/stats", response_model=CaseStatsOut, dependencies=[Depends(_READ_ROLES)])
async def case_stats_endpoint(
    session: SessionDep,
    filters: Annotated[CaseFilters, Depends(_case_filters)],
) -> CaseStatsOut:
    """Aggregate counts for the case list. Takes the same query string as ``GET /cases``
    (sort / limit / cursor are ignored) so a summary strip matches the filtered list."""
    return await case_stats(session, filters)


@router.get("/{case_id}", response_model=CaseDetailOut, dependencies=[Depends(_READ_ROLES)])
async def case_detail(case_id: UUID, session: SessionDep) -> CaseDetailOut:
    """Case header + linked alerts (with grouping rationale) + notes + timeline."""
    try:
        return await get_case_detail(session, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found") from exc


@router.post(
    "/{case_id}/transition",
    response_model=CaseOut,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
async def transition_case_endpoint(
    case_id: UUID,
    body: TransitionRequest,
    session: SessionDep,
    actor: Annotated[Principal, Depends(get_current_principal)],
    if_match: int | None = Header(default=None, alias="If-Match"),
) -> CaseOut:
    """Move a case to ``body.to``, appending a ``case.transitioned`` audit event."""
    try:
        case = await transition_case(
            session,
            case_id,
            body.to,
            body.reason,
            body.disposition,
            actor,
            expected_version=if_match,
        )
    except CaseNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found") from exc
    except StaleCaseVersion as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="stale_case_version"
        ) from exc
    except TransitionError as exc:
        if exc.code == "illegal_transition":
            http_status = status.HTTP_409_CONFLICT
        else:
            http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(status_code=http_status, detail=exc.code) from exc

    await session.commit()
    # ``updated_at`` (server ``onupdate``) and, for a just-seeded case,
    # ``created_at`` are populated by the DB, so reload before serialising.
    await session.refresh(case)
    return CaseOut.model_validate(case)


@router.post(
    "/{case_id}/assign",
    response_model=CaseOut,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
async def assign_case_endpoint(
    case_id: UUID,
    body: AssignRequest,
    session: SessionDep,
    actor: Annotated[Principal, Depends(get_current_principal)],
) -> CaseOut:
    """Assign (or, with ``assignee_id: null``, unassign) a case."""
    try:
        case = await assign_case(session, case_id, body.assignee_id, actor)
    except CaseNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found") from exc
    except CaseReadOnly as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="case_read_only") from exc
    except InvalidAssignee as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_assignee"
        ) from exc

    await session.commit()
    await session.refresh(case)
    return CaseOut.model_validate(case)


@router.post(
    "/{case_id}/notes",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
async def add_note_endpoint(
    case_id: UUID,
    body: NoteCreate,
    session: SessionDep,
    actor: Annotated[Principal, Depends(get_current_principal)],
) -> NoteOut:
    """Append an immutable note to a case."""
    try:
        note = await add_note(session, case_id, body.body, actor)
    except CaseNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found") from exc
    except CaseReadOnly as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="case_read_only") from exc

    await session.commit()
    await session.refresh(note)
    return NoteOut.model_validate(note)


@router.post(
    "/{case_id}/notes/{note_id}/retract",
    response_model=NoteOut,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
async def retract_note_endpoint(
    case_id: UUID,
    note_id: UUID,
    body: NoteRetract,
    session: SessionDep,
    actor: Annotated[Principal, Depends(get_current_principal)],
) -> NoteOut:
    """Retract a note. Author-or-admin only; a note not on ``case_id`` is a 404."""
    # Cheap pre-check that the note exists *and belongs to this case* before the
    # service mutates anything -- keeps a "wrong case" request a clean 404 with
    # no partial write. ``retract_note`` then re-loads FOR UPDATE and owns authz.
    existing = await session.get(Note, note_id)
    if existing is None or existing.case_id != case_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="note_not_found")

    try:
        note = await retract_note(session, note_id, body.reason, actor)
    except NoteNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="note_not_found") from exc
    except NoteRetractForbidden as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="note_retract_forbidden"
        ) from exc

    await session.commit()
    await session.refresh(note)
    return NoteOut.model_validate(note)


__all__ = ["router"]
