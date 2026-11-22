"""The web app keeps one shared team workspace in step with its users' roles.

Only the web app's service token may call this; a user session never can,
or any member could promote themselves.
"""

import psycopg
from core_api_helpers import WEB_SERVICE_TOKEN, as_user, bearer

ROUTE = "/api/v1/internal/team-members/{user}"
WEB = bearer(WEB_SERVICE_TOKEN)


def put(client, user, role, headers=WEB):
    return client.put(ROUTE.format(user=user), json={"role": role}, headers=headers)


def my_workspaces(client, issuer, user):
    me = client.get("/api/v1/me", headers=as_user(issuer, user)).json()
    return [(w["slug"], w["role"]) for w in me["workspaces"]]


def test_only_the_web_apps_service_token_may_set_roles(client, issuer) -> None:
    assert put(client, "alice", "owner", headers={}).status_code == 401
    assert put(client, "alice", "owner", headers=as_user(issuer, "alice")).status_code == 401
    assert put(client, "alice", "owner", headers=bearer("x" * 48)).status_code == 401
    assert my_workspaces(client, issuer, "alice") == []


def test_every_user_joins_the_same_team_workspace_with_their_role(client, issuer) -> None:
    alice = put(client, "alice", "owner")
    bob = put(client, "bob", "reader")
    assert alice.status_code == bob.status_code == 200
    assert alice.json()["data"]["workspace_id"] == bob.json()["data"]["workspace_id"]
    assert my_workspaces(client, issuer, "alice") == [("team", "owner")]
    assert my_workspaces(client, issuer, "bob") == [("team", "reader")]


def test_a_role_change_and_a_removal_take_effect(client, issuer) -> None:
    put(client, "carol", "editor")
    put(client, "carol", "reader")
    assert my_workspaces(client, issuer, "carol") == [("team", "reader")]
    removed = put(client, "carol", None)
    assert removed.status_code == 200
    assert removed.json()["data"]["role"] is None
    assert my_workspaces(client, issuer, "carol") == []


def test_only_changes_are_audited(client, db_url) -> None:
    put(client, "dave", "editor")
    put(client, "dave", "editor")
    put(client, "dave", "owner")
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT actor, action, detail->>'from', detail->>'to' FROM core.audit_events"
            " WHERE resource = 'user:dave' ORDER BY id"
        ).fetchall()
    assert rows == [
        ("web", "membership.set", None, "editor"),
        ("web", "membership.set", "editor", "owner"),
    ]


def test_a_synced_member_works_in_the_team_workspace_with_their_own_session(client, issuer) -> None:
    ws = put(client, "erin", "editor").json()["data"]["workspace_id"]
    res = client.get("/api/v1/documents", headers={**as_user(issuer, "erin"), "X-Workspace-Id": ws})
    assert res.status_code == 200


def test_an_unknown_role_is_refused(client) -> None:
    assert put(client, "frank", "admin").status_code == 400
