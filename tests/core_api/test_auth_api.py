"""core-api's auth and API-key endpoints, end to end against a real Postgres."""

import re
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient
from identity import Issuer

from core_api.config import Settings
from core_api.main import create_app

PEPPER = "pepper-for-tests-only-0123456789abcdef"


@pytest.fixture
def issuer() -> Issuer:
    return Issuer()


@pytest.fixture
def app(db_url, issuer):
    settings = Settings(DATABASE_URL=db_url, API_KEY_PEPPER=PEPPER, LOG_FORMAT="console")
    return create_app(settings, sessions=issuer.provider())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def as_user(issuer: Issuer, sub: str) -> dict[str, str]:
    return issuer.bearer("user", sub=sub)


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def new_workspace(client, issuer, sub="alice", slug="acme") -> str:
    res = client.post(
        "/api/v1/workspaces",
        json={"slug": slug, "name": slug.title()},
        headers=as_user(issuer, sub),
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


def new_key(client, issuer, ws, sub="alice", scopes=("chat",), **extra):
    res = client.post(
        f"/api/v1/workspaces/{ws}/api-keys",
        json={"name": "laptop", "scopes": list(scopes), **extra},
        headers=as_user(issuer, sub),
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]


def add_member(db_url, ws, user, role) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO core.memberships (workspace_id, user_id, role) VALUES (%s, %s, %s)",
            (ws, user, role),
        )


# --------------------------------------------------------------- mandatory


def test_every_route_but_health_needs_a_credential(app, client) -> None:
    # The OpenAPI schema lists every route the app serves, router-mounted ones
    # included, so a new endpoint is covered the moment it exists.
    paths = app.openapi()["paths"]
    checked = 0
    for path, methods in paths.items():
        if path == "/health":
            continue
        concrete = re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), path)
        for method in methods:
            res = client.request(method.upper(), concrete)
            assert res.status_code == 401, (method, path, res.text)
            assert res.json()["error"]["code"] == "unauthorized"
            checked += 1
    assert checked >= 6
    assert client.get("/health").status_code == 200


# ------------------------------------------------------------ credentials


def test_bad_credentials_are_401(client, issuer) -> None:
    for header in (
        {"Authorization": "Bearer nonsense"},
        bearer("ldk_ABCDEFGHIJKL_" + "0" * 64),  # well-formed, unknown
        issuer.bearer("user", expires_in=-120),  # expired session token
    ):
        assert client.get("/api/v1/me", headers=header).status_code == 401


def test_a_session_user_creates_a_workspace_and_owns_it(client, issuer) -> None:
    ws = new_workspace(client, issuer)
    me = client.get("/api/v1/me", headers=as_user(issuer, "alice")).json()
    assert me["via"] == "session"
    assert [(w["id"], w["role"]) for w in me["workspaces"]] == [(ws, "owner")]
    taken = client.post(
        "/api/v1/workspaces", json={"slug": "acme", "name": "x"}, headers=as_user(issuer, "bob")
    )
    assert taken.status_code == 409


def test_an_api_key_is_shown_once_and_never_stored(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    created = new_key(client, issuer, ws)
    key = created["key"]

    listed = client.get(
        f"/api/v1/workspaces/{ws}/api-keys", headers=as_user(issuer, "alice")
    ).json()["data"]
    assert [k["id"] for k in listed] == [created["id"]]
    assert "key" not in listed[0]

    with psycopg.connect(db_url) as conn:
        dump = str(conn.execute("SELECT * FROM core.api_keys").fetchall())
    assert key not in dump
    assert key.split("_")[2] not in dump  # not even the secret part

    me = client.get("/api/v1/me", headers=bearer(key)).json()
    assert me["via"] == "api_key"
    assert [w["id"] for w in me["workspaces"]] == [ws]


def test_a_key_cannot_reach_another_workspace(client, issuer) -> None:
    a = new_workspace(client, issuer, slug="a")
    b = new_workspace(client, issuer, slug="b")
    key = new_key(client, issuer, a, scopes=("chat", "manage"))["key"]
    assert client.get(f"/api/v1/workspaces/{a}/api-keys", headers=bearer(key)).status_code == 200
    assert client.get(f"/api/v1/workspaces/{b}/api-keys", headers=bearer(key)).status_code == 403


def test_non_members_and_non_owners_cannot_manage_keys(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    add_member(db_url, ws, "eve-editor", "editor")
    path = f"/api/v1/workspaces/{ws}/api-keys"
    assert client.get(path, headers=as_user(issuer, "mallory")).status_code == 403
    assert client.get(path, headers=as_user(issuer, "eve-editor")).status_code == 403
    res = client.post(path, json={"name": "x"}, headers=as_user(issuer, "eve-editor"))
    assert res.status_code == 403


def test_revoked_and_expired_keys_stop_working(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    created = new_key(client, issuer, ws)
    res = client.delete(
        f"/api/v1/workspaces/{ws}/api-keys/{created['id']}", headers=as_user(issuer, "alice")
    )
    assert res.status_code == 204
    assert client.get("/api/v1/me", headers=bearer(created["key"])).status_code == 401

    soon = new_key(
        client, issuer, ws, expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()
    )
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "UPDATE core.api_keys SET created_at = now() - interval '2 days',"
            " expires_at = now() - interval '1 second' WHERE id = %s",
            (soon["id"],),
        )
    assert client.get("/api/v1/me", headers=bearer(soon["key"])).status_code == 401


def test_another_workspace_cannot_revoke_your_key(client, issuer) -> None:
    mine = new_workspace(client, issuer, sub="alice", slug="mine")
    theirs = new_workspace(client, issuer, sub="bob", slug="theirs")
    key_id = new_key(client, issuer, mine)["id"]
    res = client.delete(
        f"/api/v1/workspaces/{theirs}/api-keys/{key_id}", headers=as_user(issuer, "bob")
    )
    assert res.status_code == 404


def test_api_keys_cannot_create_workspaces(client, issuer) -> None:
    ws = new_workspace(client, issuer)
    key = new_key(client, issuer, ws, scopes=("chat", "ingest", "manage"))["key"]
    res = client.post(
        "/api/v1/workspaces", json={"slug": "spawn", "name": "x"}, headers=bearer(key)
    )
    assert res.status_code == 403


def test_key_lifecycle_is_audited(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    created = new_key(client, issuer, ws)
    client.delete(
        f"/api/v1/workspaces/{ws}/api-keys/{created['id']}", headers=as_user(issuer, "alice")
    )
    with psycopg.connect(db_url) as conn:
        actions = [
            row[0]
            for row in conn.execute(
                "SELECT action FROM core.audit_events WHERE workspace_id = %s ORDER BY id", (ws,)
            )
        ]
    assert actions == ["workspace.create", "api_key.create", "api_key.revoke"]
