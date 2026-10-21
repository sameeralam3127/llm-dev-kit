"""Helpers shared by core-api's API tests."""

import psycopg
from identity import Issuer

from core_api.ports.models import Delta, Done
from ldk_core.errors import ServiceError

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


class FakeEmbedder:
    """Deterministic 768-d vectors. Can fail on demand, after ``ok_calls`` calls.

    By default every text gets a vector from its length; ``vectors`` maps a
    text to a fixed vector instead, so a test can control semantic matches.
    """

    name = "fake"
    model = "fake-embed"
    dimension = 768

    def __init__(
        self, *, fail: ServiceError | None = None, ok_calls: int = 0, vectors=None
    ) -> None:
        self.fail = fail
        self.ok_calls = ok_calls
        self.vectors = vectors or {}
        self.calls = 0

    async def embed(self, texts):
        self.calls += 1
        if self.fail is not None and self.calls > self.ok_calls:
            raise self.fail
        return [self.vectors.get(t) or ([(len(t) % 7 + 1) / 7.0] + [0.0] * 767) for t in texts]


def unit(i: int) -> list[float]:
    """A 768-d unit vector along axis ``i``: cosine distance 0 to itself, 1 to others."""
    v = [0.0] * 768
    v[i] = 1.0
    return v


class FakeModelClient:
    """Streams a fixed answer and records what it was sent."""

    def __init__(self, answer: str = "BLUEFIN-42 ships on 14 March [1].") -> None:
        self.answer = answer
        self.sent: list = []
        self.callers: list = []

    async def models(self):
        return ["llama3.1", "qwen2.5"]

    async def stream_chat(self, messages, *, model, caller):
        self.sent.append(list(messages))
        self.callers.append(caller)
        for word in self.answer.split(" "):
            yield Delta(word + " ")
        yield Done(model=model, tokens_in=42, tokens_out=len(self.answer.split()))
