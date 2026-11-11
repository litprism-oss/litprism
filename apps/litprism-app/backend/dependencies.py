from collections.abc import AsyncIterator
from typing import Annotated

from config import Settings, settings
from db.engine import get_db as _get_db
from db.models import Project
from fastapi import Depends, HTTPException, Request, status
from services.auth import AuthError, AuthUser, authenticate_token
from sqlalchemy.ext.asyncio import AsyncSession
from ws import ConnectionManager, ws_manager


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in _get_db():
        yield session


def get_settings() -> Settings:
    return settings


def get_ws_manager() -> ConnectionManager:
    return ws_manager


# Depend on db.engine.get_db (not the wrapper above): that is the function the routers
# and the test suite's dependency override both use.
DB = Annotated[AsyncSession, Depends(_get_db)]


def _bearer_token(request: Request) -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def get_current_user(request: Request, db: DB) -> AuthUser:
    try:
        return await authenticate_token(_bearer_token(request), db)
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
        ) from exc


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


async def require_member(user: CurrentUser) -> AuthUser:
    """Block guests (anonymous sessions) from features that cost money."""
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Sign in to use this feature"
        )
    return user


Member = Annotated[AuthUser, Depends(require_member)]


async def get_owned_project(project_id: str, user: CurrentUser, db: DB) -> Project:
    """404 (not 403) for someone else's project, so project IDs can't be probed."""
    project = await db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


OwnedProject = Annotated[Project, Depends(get_owned_project)]
