"""Helpers shared by model-gateway's tests."""

import json
import secrets

import psycopg

from ldk_core.errors import ErrorCode, ServiceError

# Random per run: these are test credentials, never real ones.
CORE_TOKEN = "core-" + secrets.token_hex(16)
WORKER_TOKEN = "worker-" + secrets.token_hex(16)
CLOUD_KEY = "test-" + secrets.token_hex(8)
WORKSPACE = "4a1f3c2e-8b7d-4e6f-9a0b-1c2d3e4f5a6b"


def as_core_api(user="alice", workspace=WORKSPACE, **extra) -> dict[str, str]:
    """Headers core-api sends when it calls on behalf of a user."""
    headers = {"Authorization": f"Bearer {CORE_TOKEN}", **extra}
    if user is not None:
        headers["X-On-Behalf-Of"] = user
    if workspace is not None:
        headers["X-Workspace-Id"] = workspace
    return headers


def as_worker() -> dict[str, str]:
    """Headers the ingest-worker sends."""
    return {"Authorization": f"Bearer {WORKER_TOKEN}"}


def chat(model: str, text: str = "hi") -> dict:
    """A ``POST /chat`` body."""
    return {"model": model, "stream": True, "messages": [{"role": "user", "content": text}]}


def sse_events(body: str) -> list[dict]:
    """Parse an SSE body into its ``data:`` events."""
    return [json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:")]


def audit_rows(db_url: str) -> list[dict]:
    """Every audit event, oldest first."""
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT actor, workspace_id::text AS workspace_id, action, model, egress,
                      request_id, detail
               FROM core.audit_events ORDER BY id"""
        )
        names = [c.name for c in cur.description]
        return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]


class FakeCloud:
    """A cloud LLM provider that records every call. Should never be called in sovereign mode."""

    def __init__(self, name: str = "openai") -> None:
        self.name = name
        self.calls: list = []

    async def list_models(self) -> list[str]:
        return ["gpt-4o"]

    async def complete(self, request) -> str:
        self.calls.append(request)
        return "cloud answer"

    async def stream(self, request):
        self.calls.append(request)
        for word in ("cloud ", "answer"):
            yield word


class FailingAudit:
    """An audit sink whose database is gone."""

    def __init__(self) -> None:
        self.attempts = 0

    async def record(self, event) -> None:
        self.attempts += 1
        raise psycopg.OperationalError("connection refused")


class BrokenStream:
    """A local provider that fails after its first piece of text."""

    name = "ollama"

    async def list_models(self) -> list[str]:
        return ["llama3.1"]

    async def complete(self, request) -> str:
        raise AssertionError("not used")

    async def stream(self, request):
        yield "partial "
        raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Ollama unreachable")
