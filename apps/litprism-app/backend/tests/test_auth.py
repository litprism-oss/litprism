"""Session 16.1 — Supabase auth: token verification, users, ownership, member-only routes,
route coverage, startup check and the WebSocket handshake.

`client` / `other_client` / `guest_client` (conftest) skip token verification and just act
as a given user. The tests that exercise real tokens use `raw_client`, which verifies
HS256 tokens signed with a test secret.
"""

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
import pytest_asyncio
from api.search import websocket_search_progress
from config import settings
from cryptography.hazmat.primitives.asymmetric import ec
from db.engine import get_db
from db.models import Project, User
from dependencies import get_current_user, get_owned_project
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from services import auth as auth_service
from services.auth import AuthError, check_auth_config, provision_user
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from ws import ConnectionManager

from main import app

SECRET = "test-secret-key-that-is-at-least-32-bytes-long"
SUPABASE_URL = "https://test.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"


def make_token(
    sub: str = "user-1",
    *,
    email: str | None = None,
    anonymous: bool = False,
    name: str | None = None,
    avatar: str | None = None,
    email_verified: bool | None = None,
    secret: str = SECRET,
    audience: str = "authenticated",
    issuer: str = ISSUER,
    expires_in: int = 3600,
    drop: tuple[str, ...] = (),
) -> str:
    now = int(time.time())
    claims: dict = {
        "sub": sub,
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "exp": now + expires_in,
        "is_anonymous": anonymous,
    }
    if email:
        claims["email"] = email
    meta = {}
    if name:
        meta["full_name"] = name
    if avatar:
        meta["avatar_url"] = avatar
    if email_verified is not None:
        meta["email_verified"] = email_verified
    if meta:
        claims["user_metadata"] = meta
    for key in drop:
        claims.pop(key)
    return jwt.encode(claims, secret, algorithm="HS256")


def bearer(**kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(**kwargs)}"}


@pytest.fixture
def auth_settings(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "supabase_url", SUPABASE_URL)
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "bootstrap_owner_email", "")
    monkeypatch.setattr(settings, "admin_emails", "")


@pytest_asyncio.fixture
async def raw_client(db, auth_settings):
    """No identity override: every request must carry a valid token."""
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _user_row(db, user_id: str) -> User | None:
    db.expire_all()
    return await db.get(User, user_id)


async def _add_project(db, owner_id: str | None, name: str = "P") -> str:
    # Foreign keys are enforced in tests (as in Postgres): the owner needs a users row.
    if owner_id is not None and await db.get(User, owner_id) is None:
        db.add(User(id=owner_id))
        await db.flush()
    project = Project(name=name, review_type="systematic", owner_id=owner_id)
    db.add(project)
    await db.commit()
    return project.id


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


async def test_no_authorization_header_is_401(raw_client):
    resp = await raw_client.get("/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not signed in"
    assert resp.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic dXNlcjpwYXNz", "Bearer", "Bearer   ", "token abc"])
async def test_malformed_authorization_header_is_401(raw_client, header):
    resp = await raw_client.get("/me", headers={"Authorization": header})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not signed in"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expires_in": -3600},
        {"audience": "someone-else"},
        {"issuer": "https://evil.example.com/auth/v1"},
        {"secret": "a-different-secret-that-is-32-bytes-or-more"},
        {"drop": ("sub",)},
        {"drop": ("exp",)},
    ],
    ids=["expired", "wrong-aud", "wrong-iss", "bad-signature", "no-sub", "no-exp"],
)
async def test_invalid_token_is_401(raw_client, kwargs):
    resp = await raw_client.get("/me", headers=bearer(**kwargs))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Session expired — sign in again"


async def test_garbage_token_is_401(raw_client):
    resp = await raw_client.get("/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


async def test_unsigned_alg_none_token_is_rejected(raw_client):
    now = int(time.time())
    claims = {"sub": "u", "aud": "authenticated", "iss": ISSUER, "exp": now + 3600}
    token = jwt.encode(claims, key=None, algorithm="none")
    resp = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_valid_token_returns_profile(raw_client):
    resp = await raw_client.get(
        "/me",
        headers=bearer(sub="u-1", email="Ada@Example.com", name="Ada L", avatar="https://a/x.png"),
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "id": "u-1",
        "email": "Ada@Example.com",
        "display_name": "Ada L",
        "avatar_url": "https://a/x.png",
        "is_anonymous": False,
        "is_admin": False,
    }


async def test_anonymous_token_is_a_guest(raw_client):
    resp = await raw_client.get("/me", headers=bearer(sub="g-1", anonymous=True))
    body = resp.json()
    assert resp.status_code == 200
    assert body["is_anonymous"] is True
    assert body["email"] is None


# --- asymmetric (JWKS) path -------------------------------------------------


class _FakeJWKS:
    def __init__(self, public_key=None, error: Exception | None = None):
        self.public_key = public_key
        self.error = error

    def get_signing_key_from_jwt(self, token):
        if self.error:
            raise self.error
        return SimpleNamespace(key=self.public_key)


def _es256_token(private_key, **overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": "es-user",
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": now + 3600,
        **overrides,
    }
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": "k1"})


@pytest.fixture
def jwks_mode(monkeypatch, auth_settings):
    """Verify via JWKS (no HS256 secret) against a throwaway EC key."""
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    private_key = ec.generate_private_key(ec.SECP256R1())
    fake = _FakeJWKS(private_key.public_key())
    monkeypatch.setattr(auth_service, "_jwks_client", lambda issuer: fake)
    return private_key, fake


async def test_es256_token_verified_via_jwks(raw_client, jwks_mode):
    private_key, _ = jwks_mode
    resp = await raw_client.get(
        "/me", headers={"Authorization": f"Bearer {_es256_token(private_key)}"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "es-user"


async def test_token_signed_with_another_key_is_rejected_in_jwks_mode(raw_client, jwks_mode):
    other_key = ec.generate_private_key(ec.SECP256R1())
    resp = await raw_client.get(
        "/me", headers={"Authorization": f"Bearer {_es256_token(other_key)}"}
    )
    assert resp.status_code == 401


async def test_hs256_token_is_rejected_in_jwks_mode(raw_client, jwks_mode):
    """A token must not be able to pick a symmetric algorithm against the public key."""
    resp = await raw_client.get("/me", headers=bearer())
    assert resp.status_code == 401


async def test_key_service_outage_is_503_not_401(raw_client, jwks_mode):
    private_key, fake = jwks_mode
    fake.error = jwt.PyJWKClientConnectionError("jwks unreachable")
    resp = await raw_client.get(
        "/me", headers={"Authorization": f"Bearer {_es256_token(private_key)}"}
    )
    assert resp.status_code == 503
    assert "WWW-Authenticate" not in resp.headers


async def test_unconfigured_auth_is_503(raw_client, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(settings, "supabase_url", "")
    resp = await raw_client.get("/me", headers=bearer())
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# User provisioning
# ---------------------------------------------------------------------------


async def test_first_request_creates_user_row_once(raw_client, db):
    for _ in range(3):
        resp = await raw_client.get("/me", headers=bearer(sub="u-1", email="a@example.com"))
        assert resp.status_code == 200
    count = (await db.execute(select(func.count()).select_from(User))).scalar()
    assert count == 1
    row = await _user_row(db, "u-1")
    assert row.email == "a@example.com"
    assert row.is_anonymous is False


async def test_profile_changes_are_synced(raw_client, db):
    await raw_client.get("/me", headers=bearer(sub="u-1", name="Old Name"))
    await raw_client.get("/me", headers=bearer(sub="u-1", name="New Name", avatar="https://a/b"))
    row = await _user_row(db, "u-1")
    assert row.display_name == "New Name"
    assert row.avatar_url == "https://a/b"


async def test_guest_linking_a_provider_keeps_the_same_user(raw_client, db):
    """Supabase keeps the user id when a guest links Google; is_anonymous flips."""
    await raw_client.get("/me", headers=bearer(sub="g-1", anonymous=True))
    assert (await _user_row(db, "g-1")).is_anonymous is True

    resp = await raw_client.get("/me", headers=bearer(sub="g-1", email="a@example.com"))
    assert resp.json()["is_anonymous"] is False
    row = await _user_row(db, "g-1")
    assert row.is_anonymous is False
    assert row.email == "a@example.com"
    count = (await db.execute(select(func.count()).select_from(User))).scalar()
    assert count == 1


async def test_concurrent_first_insert_does_not_fail(db, monkeypatch):
    """Parallel first requests race to insert the same user: the loser must recover."""
    profile = {
        "email": "a@example.com",
        "display_name": None,
        "avatar_url": None,
        "is_anonymous": False,
        "email_verified": True,
    }
    db.add(User(id="racer", email="a@example.com"))  # the request that won the race
    await db.commit()

    real_get = db.get
    stale = {"first": True}

    async def stale_get(model, pk, *args, **kwargs):
        if stale["first"] and model is User:
            stale["first"] = False
            return None  # this request read before the winner committed
        return await real_get(model, pk, *args, **kwargs)

    monkeypatch.setattr(db, "get", stale_get)
    user = await provision_user(db, "racer", profile)

    assert user.id == "racer"
    count = (await db.execute(select(func.count()).select_from(User))).scalar()
    assert count == 1


async def test_integrity_error_is_only_swallowed_once(db, monkeypatch):
    """A persistent failure must surface, not loop or be hidden."""

    async def boom():
        raise IntegrityError("insert", {}, Exception("always"))

    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(IntegrityError):
        await provision_user(
            db,
            "u",
            {
                "email": None,
                "display_name": None,
                "avatar_url": None,
                "is_anonymous": True,
                "email_verified": True,
            },
        )


async def test_last_seen_is_refreshed_only_when_stale(raw_client, db):
    headers = bearer(sub="u-1")
    await raw_client.get("/me", headers=headers)
    row = await _user_row(db, "u-1")

    recent = datetime.now(UTC) - timedelta(minutes=10)
    row.last_seen_at = recent
    await db.commit()
    await raw_client.get("/me", headers=headers)
    row = await _user_row(db, "u-1")
    assert row.last_seen_at.replace(tzinfo=UTC) == recent  # within the hour: untouched

    row.last_seen_at = datetime.now(UTC) - timedelta(hours=3)
    await db.commit()
    await raw_client.get("/me", headers=headers)
    row = await _user_row(db, "u-1")
    assert datetime.now(UTC) - row.last_seen_at.replace(tzinfo=UTC) < timedelta(minutes=1)


# ---------------------------------------------------------------------------
# Bootstrap owner + admin
# ---------------------------------------------------------------------------


async def test_bootstrap_owner_claims_ownerless_projects(raw_client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_owner_email", "Owner@Example.com")
    old = await _add_project(db, None, "Pre-auth project")

    other = await raw_client.get("/me", headers=bearer(sub="u-other", email="other@example.com"))
    assert other.status_code == 200
    assert (await db.get(Project, old)).owner_id is None

    await raw_client.get("/me", headers=bearer(sub="u-owner", email="owner@example.com"))
    db.expire_all()
    assert (await db.get(Project, old)).owner_id == "u-owner"

    listed = await raw_client.get("/projects", headers=bearer(sub="u-owner"))
    assert [p["id"] for p in listed.json()] == [old]


async def test_bootstrap_happens_once(raw_client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_owner_email", "owner@example.com")
    headers = bearer(sub="u-owner", email="owner@example.com")
    await raw_client.get("/me", headers=headers)
    later = await _add_project(db, None, "Appeared later")
    await raw_client.get("/me", headers=headers)
    db.expire_all()
    assert (await db.get(Project, later)).owner_id is None


async def test_bootstrap_when_a_guest_links_the_owner_email(raw_client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_owner_email", "owner@example.com")
    old = await _add_project(db, None)
    await raw_client.get("/me", headers=bearer(sub="u-1", anonymous=True))
    db.expire_all()
    assert (await db.get(Project, old)).owner_id is None

    await raw_client.get("/me", headers=bearer(sub="u-1", email="owner@example.com"))
    db.expire_all()
    assert (await db.get(Project, old)).owner_id == "u-1"


async def test_unverified_email_never_claims_projects(raw_client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_owner_email", "owner@example.com")
    old = await _add_project(db, None)
    await raw_client.get(
        "/me", headers=bearer(sub="u-x", email="owner@example.com", email_verified=False)
    )
    db.expire_all()
    assert (await db.get(Project, old)).owner_id is None


async def test_admin_flag_follows_verified_admin_email(raw_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", " Boss@Example.com , other@x.org")
    boss = await raw_client.get("/me", headers=bearer(sub="b", email="boss@example.com"))
    assert boss.json()["is_admin"] is True
    spoof = await raw_client.get(
        "/me", headers=bearer(sub="s", email="boss@example.com", email_verified=False)
    )
    assert spoof.json()["is_admin"] is False
    nobody = await raw_client.get("/me", headers=bearer(sub="n", email="nobody@example.com"))
    assert nobody.json()["is_admin"] is False


# ---------------------------------------------------------------------------
# AUTH_DISABLED (local dev)
# ---------------------------------------------------------------------------


async def test_auth_disabled_acts_as_dev_user_and_adopts_old_projects(raw_client, db, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    old = await _add_project(db, None, "Local project from before auth")

    me = await raw_client.get("/me")  # no token at all
    assert me.status_code == 200
    assert me.json()["id"] == "dev-user"

    listed = await raw_client.get("/projects")
    assert [p["id"] for p in listed.json()] == [old]
    created = await raw_client.post("/projects", json={"name": "New", "review_type": "systematic"})
    assert created.status_code == 201


async def test_auth_disabled_ignores_a_bad_token(raw_client, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    resp = await raw_client.get("/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


async def test_projects_are_listed_per_owner(client, other_client):
    mine = (
        await client.post("/projects", json={"name": "Mine", "review_type": "systematic"})
    ).json()
    theirs = (
        await other_client.post("/projects", json={"name": "Theirs", "review_type": "scoping"})
    ).json()

    assert [p["id"] for p in (await client.get("/projects")).json()] == [mine["id"]]
    assert [p["id"] for p in (await other_client.get("/projects")).json()] == [theirs["id"]]


async def test_project_is_owned_by_the_creator(client, db):
    created = (
        await client.post("/projects", json={"name": "Mine", "review_type": "systematic"})
    ).json()
    assert (await db.get(Project, created["id"])).owner_id == "test-user"
    assert "owner_id" not in created


async def test_other_users_project_is_404_for_get_patch_delete(client, other_client, project_id):
    expected = (await client.get("/projects/00000000-0000-0000-0000-000000000000")).json()

    get = await other_client.get(f"/projects/{project_id}")
    patch = await other_client.patch(f"/projects/{project_id}", json={"name": "Hijacked"})
    delete = await other_client.delete(f"/projects/{project_id}")

    for resp in (get, patch, delete):
        assert resp.status_code == 404
        assert resp.json() == expected  # indistinguishable from a project that doesn't exist

    still_there = await client.get(f"/projects/{project_id}")
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "Test Project"


# Every project-scoped route, by router. The body is deliberately absent or empty:
# the ownership check must fire before request validation, so a stranger sees 404, not 422.
PROJECT_ROUTES = [
    ("GET", "/criteria"),
    ("GET", "/criteria/history"),
    ("GET", "/criteria/1"),
    ("POST", "/criteria"),
    ("GET", "/screening/stale-count"),
    ("POST", "/screening/preview"),
    ("POST", "/screening/run"),
    ("GET", "/screening/runs"),
    ("GET", "/screening/runs/r1"),
    ("PATCH", "/screening/runs/r1"),
    ("POST", "/screening/runs/r1/resume"),
    ("POST", "/screening/runs/r1/cancel"),
    ("POST", "/screening/runs/r1/retry-failed"),
    ("DELETE", "/screening/runs/r1"),
    ("GET", "/screening/results"),
    ("POST", "/screening/a1/override"),
    ("GET", "/screening/fulltext-eligibility"),
    ("POST", "/screening/fulltext-run"),
    ("POST", "/upload"),
    ("GET", "/uploads"),
    ("GET", "/prisma-counts"),
    ("GET", "/export/csv"),
    ("GET", "/export/prisma-s"),
    ("POST", "/fulltext/retrieve"),
    ("GET", "/fulltext/status"),
    ("POST", "/search-runs/preview"),
    ("POST", "/search-runs"),
    ("GET", "/search-runs"),
    ("GET", "/search-runs/r1"),
    ("PATCH", "/search-runs/r1"),
    ("POST", "/search-runs/r1/execute"),
    ("GET", "/search-runs/r1/articles"),
    ("GET", "/articles"),
    ("GET", "/enrichment/status"),
]


def _is_project_not_found(resp) -> bool:
    if resp.status_code != 404:
        return False
    try:
        return resp.json().get("detail") == "Project not found"
    except ValueError:  # not JSON (e.g. a file download)
        return False


@pytest.mark.parametrize(("method", "suffix"), PROJECT_ROUTES)
async def test_strangers_get_404_on_every_project_route(
    client, other_client, project_id, method, suffix
):
    resp = await other_client.request(method, f"/projects/{project_id}{suffix}")
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Project not found"


@pytest.mark.parametrize(("method", "suffix"), PROJECT_ROUTES)
async def test_owner_gets_past_the_ownership_check_on_every_project_route(
    client, project_id, method, suffix
):
    resp = await client.request(method, f"/projects/{project_id}{suffix}")
    assert not _is_project_not_found(resp), resp.text


def test_project_routes_list_is_complete():
    """PROJECT_ROUTES above must cover every project-scoped HTTP route in the app."""
    declared = {(m, p) for m, p in PROJECT_ROUTES}
    actual = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or "{project_id}" not in route.path:
            continue
        tail = route.path.split("{project_id}", 1)[1]
        tail = tail.replace("{run_id}", "r1").replace("{article_id}", "a1")
        tail = tail.replace("{version}", "1").replace("{fmt}", "csv")
        for method in route.methods:
            if tail:  # "/projects/{project_id}" itself is covered by its own tests
                actual.add((method, tail))
    undeclared = {r for r in actual if r not in declared}
    assert not undeclared, f"add to PROJECT_ROUTES: {sorted(undeclared)}"


# ---------------------------------------------------------------------------
# Guests
# ---------------------------------------------------------------------------

MEMBER_ONLY_ROUTES = [
    ("POST", "/screening/run"),
    ("POST", "/screening/runs/r1/resume"),
    ("POST", "/screening/runs/r1/retry-failed"),
    ("POST", "/screening/fulltext-run"),
    ("POST", "/fulltext/retrieve"),
]


@pytest.fixture
async def guest_project_id(guest_client):
    resp = await guest_client.post("/projects", json={"name": "Guest", "review_type": "rapid"})
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.parametrize(("method", "suffix"), MEMBER_ONLY_ROUTES)
async def test_guest_is_blocked_from_member_only_routes(
    guest_client, guest_project_id, method, suffix
):
    body = {"stage": "abstract"} if suffix == "/screening/run" else None
    resp = await guest_client.request(method, f"/projects/{guest_project_id}{suffix}", json=body)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Sign in to use this feature"


@pytest.mark.parametrize(("method", "suffix"), MEMBER_ONLY_ROUTES)
async def test_member_is_not_blocked_from_member_only_routes(client, project_id, method, suffix):
    body = {"stage": "abstract"} if suffix == "/screening/run" else None
    resp = await client.request(method, f"/projects/{project_id}{suffix}", json=body)
    assert resp.status_code != 403, resp.text


async def test_guest_gets_404_not_403_on_someone_elses_project(guest_client, project_id):
    """Ownership is checked first, so a guest can't tell a member project exists."""
    resp = await guest_client.post(f"/projects/{project_id}/screening/run", json={})
    assert resp.status_code == 404


async def test_guest_can_use_the_free_features(guest_client, guest_project_id, mock_screener):
    pid = guest_project_id
    criteria = await guest_client.post(
        f"/projects/{pid}/criteria", json={"inclusion": ["RCT"], "exclusion": []}
    )
    assert criteria.status_code == 201

    preview = await guest_client.post(
        f"/projects/{pid}/screening/preview",
        json={
            "criteria": {"inclusion": ["RCT"], "exclusion": []},
            "articles": [{"id": "t1", "title": "A trial", "abstract": "RCT"}],
        },
    )
    assert preview.status_code == 200

    assert (await guest_client.get(f"/projects/{pid}/articles")).status_code == 200
    assert (await guest_client.get(f"/projects/{pid}/export/csv")).status_code == 200
    assert (await guest_client.get(f"/projects/{pid}/prisma-counts")).status_code == 200
    assert (await guest_client.get("/me")).json()["is_anonymous"] is True


# ---------------------------------------------------------------------------
# Route coverage: a new route can't silently skip authentication
# ---------------------------------------------------------------------------


def _dependency_calls(dependant):
    yield dependant.call
    for sub in dependant.dependencies:
        yield from _dependency_calls(sub)


def test_every_project_route_checks_ownership():
    missing = [
        f"{sorted(route.methods)} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute)
        and "{project_id}" in route.path
        and get_owned_project not in set(_dependency_calls(route.dependant))
    ]
    assert not missing, f"routes without get_owned_project: {missing}"


PUBLIC_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def test_chat_stub_router_is_guarded_before_it_has_any_routes():
    from api.chat import router as chat_router

    assert [d.dependency for d in chat_router.dependencies] == [get_current_user]


def test_every_http_route_requires_authentication():
    open_routes = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in PUBLIC_PATHS:
            continue
        if get_current_user not in set(_dependency_calls(route.dependant)):
            open_routes.append(f"{sorted(route.methods)} {route.path}")
    assert not open_routes, f"routes open to anyone: {open_routes}"


def test_the_only_websocket_route_is_the_authenticated_handshake():
    ws_routes = [r for r in app.routes if r.__class__.__name__ == "APIWebSocketRoute"]
    assert [r.path for r in ws_routes] == ["/ws/{project_id}"]
    assert ws_routes[0].endpoint is websocket_search_progress


# ---------------------------------------------------------------------------
# Startup check
# ---------------------------------------------------------------------------


def test_startup_refuses_to_run_open_without_supabase(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "supabase_url", "")
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        check_auth_config()


def test_startup_ok_with_supabase_configured(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "supabase_url", SUPABASE_URL)
    check_auth_config()


def test_startup_warns_loudly_when_auth_is_disabled(monkeypatch, caplog):
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "supabase_url", "")
    with caplog.at_level("WARNING"):
        check_auth_config()
    assert "AUTH_DISABLED" in caplog.text


# ---------------------------------------------------------------------------
# WebSocket handshake
# ---------------------------------------------------------------------------


class FakeWebSocket:
    """Just enough of starlette's WebSocket for the handler."""

    def __init__(self, first_message=None, *, hang=False, error: Exception | None = None):
        self.first_message = first_message
        self.hang = hang
        self.error = error
        self.accepted = False
        self.close_code: int | None = None
        self.registered_during_loop = False
        self.on_loop = None  # called once the handshake passed and the socket idles
        self.manager: ConnectionManager | None = None
        self.project_id = ""
        self.received_json = False

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        self.received_json = True
        if self.hang:
            await asyncio.sleep(3600)
        if self.error:
            raise self.error
        if isinstance(self.first_message, Exception):
            raise self.first_message
        return self.first_message

    async def receive_text(self):
        # Reached only once the handshake passed; record whether the socket was registered.
        conns = self.manager._connections.get(self.project_id, [])
        self.registered_during_loop = self in conns
        if self.on_loop:
            self.on_loop()
        raise WebSocketDisconnect()

    async def close(self, code: int = 1000):
        self.close_code = code


async def _handshake(db, project_id: str, ws: FakeWebSocket) -> ConnectionManager:
    manager = ConnectionManager()
    ws.manager, ws.project_id = manager, project_id
    await websocket_search_progress(project_id, ws, manager, db)
    return manager


@pytest.fixture
def fast_ws_timeout(monkeypatch):
    monkeypatch.setattr("api.search._WS_AUTH_TIMEOUT_SECONDS", 0.05)


async def test_ws_owner_with_valid_token_is_registered(db, auth_settings):
    project_id = await _add_project(db, "u-owner")
    ws = FakeWebSocket({"token": make_token(sub="u-owner")})
    manager = await _handshake(db, project_id, ws)

    assert ws.accepted
    assert ws.close_code is None
    assert ws.registered_during_loop
    assert manager._connections[project_id] == []  # removed again on disconnect


async def test_ws_releases_its_db_connection_before_idling(db, auth_settings, monkeypatch):
    """An open socket idles for as long as the page is open: it must not pin a pooled connection."""
    closed: list[bool] = []
    real_close = db.close

    async def spy_close():
        closed.append(True)
        await real_close()

    monkeypatch.setattr(db, "close", spy_close)
    project_id = await _add_project(db, "u-owner")
    ws = FakeWebSocket({"token": make_token(sub="u-owner")})
    closed_when_idle: list[bool] = []
    ws.on_loop = lambda: closed_when_idle.append(bool(closed))
    await _handshake(db, project_id, ws)
    assert closed_when_idle == [True]


async def test_ws_releases_its_db_connection_when_refusing(db, auth_settings, monkeypatch):
    closed: list[bool] = []
    real_close = db.close

    async def spy_close():
        closed.append(True)
        await real_close()

    monkeypatch.setattr(db, "close", spy_close)
    project_id = await _add_project(db, "u-owner")
    await _handshake(db, project_id, FakeWebSocket({"token": make_token(sub="u-intruder")}))
    assert closed == [True]


async def test_ws_guest_can_watch_their_own_project(db, auth_settings):
    project_id = await _add_project(db, "g-1")
    ws = FakeWebSocket({"token": make_token(sub="g-1", anonymous=True)})
    await _handshake(db, project_id, ws)
    assert ws.close_code is None
    assert ws.registered_during_loop


async def test_ws_other_users_project_is_refused(db, auth_settings):
    project_id = await _add_project(db, "u-owner")
    ws = FakeWebSocket({"token": make_token(sub="u-intruder")})
    manager = await _handshake(db, project_id, ws)

    assert ws.close_code == 4401
    assert not ws.registered_during_loop
    assert manager._connections.get(project_id, []) == []


async def test_ws_unknown_project_is_refused(db, auth_settings):
    ws = FakeWebSocket({"token": make_token(sub="u-1")})
    await _handshake(db, "does-not-exist", ws)
    assert ws.close_code == 4401


@pytest.mark.parametrize(
    "first_message",
    [
        {"token": "garbage"},
        {"token": make_token(expires_in=-3600)},
        {"token": 12345},
        {"nothing": "here"},
        ["not", "a", "dict"],
        None,
        json.JSONDecodeError("bad", "doc", 0),
        KeyError("text"),  # binary frame: starlette has no "text" key
    ],
    ids=[
        "garbage",
        "expired",
        "non-string",
        "no-token-key",
        "list",
        "null",
        "not-json",
        "binary",
    ],
)
async def test_ws_bad_first_message_is_refused(db, auth_settings, first_message):
    project_id = await _add_project(db, "user-1")
    ws = FakeWebSocket(first_message)
    await _handshake(db, project_id, ws)
    assert ws.close_code == 4401
    assert not ws.registered_during_loop


async def test_ws_silent_client_is_dropped_after_the_timeout(db, auth_settings, fast_ws_timeout):
    project_id = await _add_project(db, "user-1")
    ws = FakeWebSocket(hang=True)
    await _handshake(db, project_id, ws)
    assert ws.close_code == 4401
    assert not ws.registered_during_loop


async def test_ws_client_leaving_during_handshake_is_not_an_error(db, auth_settings):
    project_id = await _add_project(db, "user-1")
    ws = FakeWebSocket(error=WebSocketDisconnect())
    await _handshake(db, project_id, ws)
    assert ws.close_code is None


async def test_ws_key_service_outage_asks_the_client_to_retry(db, jwks_mode):
    private_key, fake = jwks_mode
    fake.error = jwt.PyJWKClientConnectionError("down")
    project_id = await _add_project(db, "es-user")
    ws = FakeWebSocket({"token": _es256_token(private_key)})
    await _handshake(db, project_id, ws)
    assert ws.close_code == 1013


async def test_ws_with_auth_disabled_needs_no_handshake(db, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    project_id = await _add_project(db, None, "Pre-auth project")
    ws = FakeWebSocket()
    await _handshake(db, project_id, ws)

    assert not ws.received_json  # must not wait 5s for a message nobody will send
    assert ws.close_code is None
    assert ws.registered_during_loop


def test_ws_over_a_real_socket_without_a_token_is_closed_4401(auth_settings, fast_ws_timeout):
    """Through the real router: no first message means the connection is refused."""
    with (
        TestClient(app).websocket_connect("/ws/some-project") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.receive_text()
    assert exc.value.code == 4401


def test_ws_over_a_real_socket_with_a_bad_token_is_closed_4401(auth_settings):
    with (
        TestClient(app).websocket_connect("/ws/some-project") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.send_json({"token": "garbage"})
        ws.receive_text()
    assert exc.value.code == 4401


def test_auth_error_carries_its_status():
    assert AuthError("x").status_code == 401
    assert AuthError("x", 503).status_code == 503
