"""Response bodies for the ``/api/v1/users`` endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

__all__ = ["UserOut"]


class UserOut(BaseModel):
    """A user as returned by ``GET /api/v1/users`` -- just what an assignee picker needs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
