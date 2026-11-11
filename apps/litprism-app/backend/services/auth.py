"""Supabase access-token verification and user provisioning.

Shared by the HTTP dependency (dependencies.get_current_user) and the WebSocket
handshake, which can't use Depends() for the token.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from config import settings
from db.models import Project, User
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_AUDIENCE = "authenticated"
_CLOCK_SKEW_SECONDS = 10
_LAST_SEEN_REFRESH = timedelta(hours=1)


class AuthError(Exception):
    """Raised for a missing/invalid token (401) or an unreachable key service (503)."""

    def __init__(self, detail: str, status_code: int = 401) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None
    is_anonymous: bool
    is_admin: bool
    display_name: str | None = None
    avatar_url: str | None = None


DEV_USER = AuthUser(
    id="dev-user",
    email="dev@localhost",
    is_anonymous=False,
    is_admin=True,
    display_name="Dev User",
)


def _issuer() -> str | None:
    if not settings.supabase_url:
        return None
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


@lru_cache(maxsize=4)
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", cache_keys=True)


def _decode(token: str) -> dict[str, Any]:
    """Blocking: PyJWKClient fetches keys with urllib. Call via verify_token."""
    issuer = _issuer()
    common: dict[str, Any] = {
        "audience": _AUDIENCE,
        "issuer": issuer,
        "options": {"require": ["exp", "sub"]},
        "leeway": _CLOCK_SKEW_SECONDS,
    }
    try:
        if settings.supabase_jwt_secret:
            return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], **common)
        if issuer is None:
            raise AuthError("Auth is not configured", 503)
        # Asymmetric algorithms only: never let a token pick HS256 against a public key.
        key = _jwks_client(issuer).get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["ES256", "RS256"], **common)
    except jwt.PyJWKClientConnectionError as exc:
        raise AuthError("Auth service unavailable", 503) from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Session expired — sign in again") from exc


async def verify_token(token: str) -> dict[str, Any]:
    """Return the claims of a valid Supabase access token, else raise AuthError."""
    return await asyncio.to_thread(_decode, token)


def _aware(dt: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _profile(claims: dict[str, Any]) -> dict[str, Any]:
    meta = claims.get("user_metadata") or {}
    return {
        "email": claims.get("email") or None,
        "display_name": meta.get("full_name") or meta.get("name") or None,
        "avatar_url": meta.get("avatar_url") or meta.get("picture") or None,
        "is_anonymous": bool(claims.get("is_anonymous", False)),
        # Google and GitHub always set this. Treat only an explicit False as unverified.
        "email_verified": meta.get("email_verified") is not False,
    }


def _is_admin(email: str | None, verified: bool) -> bool:
    return bool(email and verified and email.lower() in settings.admin_email_list)


async def _claim_ownerless_projects(db: AsyncSession, user_id: str) -> None:
    await db.execute(update(Project).where(Project.owner_id.is_(None)).values(owner_id=user_id))


async def _upsert_user(db: AsyncSession, user_id: str, profile: dict[str, Any]) -> bool:
    """Create or refresh the users row. Returns True when the user just became a member
    (newly created as non-anonymous, or a guest who just linked a provider)."""
    now = datetime.now(UTC)
    user = await db.get(User, user_id)
    became_member = False
    if user is None:
        user = User(
            id=user_id,
            email=profile["email"],
            display_name=profile["display_name"],
            avatar_url=profile["avatar_url"],
            is_anonymous=profile["is_anonymous"],
            created_at=now,
            last_seen_at=now,
        )
        db.add(user)
        became_member = not profile["is_anonymous"]
    else:
        became_member = user.is_anonymous and not profile["is_anonymous"]
        for field in ("email", "display_name", "avatar_url", "is_anonymous"):
            if getattr(user, field) != profile[field]:
                setattr(user, field, profile[field])
        if now - _aware(user.last_seen_at) > _LAST_SEEN_REFRESH:
            user.last_seen_at = now
    return became_member


async def provision_user(
    db: AsyncSession,
    user_id: str,
    profile: dict[str, Any],
    *,
    claim_ownerless: bool = False,
) -> AuthUser:
    """Upsert the users row for a verified identity and return the AuthUser.

    claim_ownerless hands every ownerless (pre-auth) project to the user when they first
    become a member. It is on for the AUTH_DISABLED dev user; in production the same
    handover is limited to BOOTSTRAP_OWNER_EMAIL.

    Several requests from a brand-new user arrive at once (the frontend fires them in
    parallel on first load), so a concurrent insert of the same primary key is expected:
    roll back and re-read instead of failing.
    """
    try:
        became_member = await _upsert_user(db, user_id, profile)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        became_member = await _upsert_user(db, user_id, profile)
        await db.commit()

    email = profile["email"]
    verified = profile["email_verified"]
    owner_email = settings.bootstrap_owner_email.strip().lower()
    is_bootstrap_owner = bool(verified and email and owner_email and email.lower() == owner_email)
    if became_member and (claim_ownerless or is_bootstrap_owner):
        await _claim_ownerless_projects(db, user_id)
        await db.commit()

    return AuthUser(
        id=user_id,
        email=email,
        is_anonymous=profile["is_anonymous"],
        is_admin=_is_admin(email, verified),
        display_name=profile["display_name"],
        avatar_url=profile["avatar_url"],
    )


async def authenticate_token(token: str | None, db: AsyncSession) -> AuthUser:
    """Verify a bearer token and return its user. Raises AuthError on any failure.

    With AUTH_DISABLED every call returns the fixed dev user, whatever the token.
    """
    if settings.auth_disabled:
        await provision_user(
            db,
            DEV_USER.id,
            {
                "email": DEV_USER.email,
                "display_name": DEV_USER.display_name,
                "avatar_url": None,
                "is_anonymous": False,
                "email_verified": True,
            },
            claim_ownerless=True,
        )
        return DEV_USER
    if not token:
        raise AuthError("Not signed in")
    claims = await verify_token(token)
    return await provision_user(db, claims["sub"], _profile(claims))


async def owns_project(db: AsyncSession, project_id: str, user_id: str) -> bool:
    project = await db.get(Project, project_id)
    return project is not None and project.owner_id == user_id


def check_auth_config() -> None:
    """Called at startup: refuse to run open by accident."""
    if settings.auth_disabled:
        logger.warning(
            "AUTH_DISABLED is on: every request runs as the dev user. Never use in production."
        )
    elif not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is required unless AUTH_DISABLED=true")
