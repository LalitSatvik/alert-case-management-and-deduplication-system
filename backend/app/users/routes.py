"""``/api/v1/users`` -- the directory an investigator console needs for assignment.

Read-only and deliberately minimal: it returns active users (id, email, display
name) so the case assignee control can offer a searchable picker instead of a
raw UUID field. All read roles may call it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db import get_session
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "",
    response_model=list[UserOut],
    dependencies=[Depends(require_role("analyst", "admin", "readonly"))],
)
async def list_users(session: SessionDep) -> list[UserOut]:
    """Active users, ordered by email, for the assignee picker."""
    rows = (
        (await session.execute(select(User).where(User.is_active.is_(True)).order_by(User.email)))
        .scalars()
        .all()
    )
    return [UserOut.model_validate(row) for row in rows]


__all__ = ["router"]
