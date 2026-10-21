"""Helpers shared by core-api's API tests."""

import psycopg
from identity import Issuer

PEPPER = "pepper-for-tests-only-0123456789abcdef"


def as_user(issuer: Issuer, sub: str) -> dict[str, str]:
    """Headers for a signed-in user."""
    return issuer.bearer("user", sub=sub)


def bearer(key: str) -> dict[str, str]:
    """Headers for an API key."""
    return {"Authorization": f"Bearer {key}"}


def new_workspace(client, issuer, sub="alice", slug="acme") -> str:
    """Create a workspace owned by ``sub``; return its id."""
    res = client.post(
        "/api/v1/workspaces",
        json={"slug": slug, "name": slug.title()},
        headers=as_user(issuer, sub),
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


def new_key(client, issuer, ws, sub="alice", scopes=("chat",), **extra):
    """Issue an API key in ``ws``; return the created record, key included."""
    res = client.post(
        f"/api/v1/workspaces/{ws}/api-keys",
        json={"name": "laptop", "scopes": list(scopes), **extra},
        headers=as_user(issuer, sub),
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]


def add_member(db_url, ws, user, role) -> None:
    """Add a member directly; there is no membership endpoint yet."""
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO core.memberships (workspace_id, user_id, role) VALUES (%s, %s, %s)",
            (ws, user, role),
        )
