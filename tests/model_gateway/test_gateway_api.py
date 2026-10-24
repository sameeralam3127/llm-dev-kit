"""model-gateway's HTTP API: service auth, streaming, embedding and fail-closed audit."""

import asyncio
import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from gateway_helpers import (
    CORE_TOKEN,
    WORKER_TOKEN,
    WORKSPACE,
    BrokenStream,
    FailingAudit,
    as_core_api,
    as_worker,
    audit_rows,
    chat,
    sse_events,
)

from core_api.adapters.gateway import GatewayEmbedder, GatewayModelClient
from core_api.domain.retrieval import ChatMessage
from core_api.ports.models import Delta, Done, OnBehalfOf
from ldk_core.errors import ErrorCode, ServiceError


def model_calls(ollama) -> list[str]:
    return [path for path, _ in ollama.requests if path != "/api/tags"]


# ------------------------------------------------------------------- auth


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/models", None),
        ("POST", "/chat", chat("llama3.1")),
        ("POST", "/embed", {"texts": ["a"]}),
    ],
)
def test_every_route_but_health_needs_a_service_token(client, method, path, body) -> None:
    for headers in ({}, {"Authorization": "Bearer not-a-service"}, {"Authorization": CORE_TOKEN}):
        res = client.request(method, path, json=body, headers=headers)
        assert res.status_code == 401, (headers, res.text)
        assert res.json()["error"]["code"] == "unauthorized"
    assert client.get("/health").status_code == 200


def test_the_worker_may_only_embed(client, db_url, ollama) -> None:
    assert client.get("/models", headers=as_worker()).status_code == 403
    res = client.post("/chat", json=chat("llama3.1"), headers=as_worker())
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "forbidden"
    assert model_calls(ollama) == []

    res = client.post("/embed", json={"texts": ["a", "b"]}, headers=as_worker())
    assert res.status_code == 200, res.text
    assert [(r["actor"], r["action"]) for r in audit_rows(db_url)] == [
        ("service:ingest-worker", "model.embed")
    ]


def test_chat_must_say_on_whose_behalf(client, ollama) -> None:
    for headers in (as_core_api(user=None), as_core_api(workspace=None)):
        res = client.post("/chat", json=chat("llama3.1"), headers=headers)
        assert res.status_code == 400, res.text
    res = client.post("/chat", json=chat("llama3.1"), headers=as_core_api(workspace="nope"))
    assert res.status_code == 400
    assert model_calls(ollama) == []


# ------------------------------------------------------------------- chat


def test_streams_a_local_answer_and_audits_it_first(client, db_url) -> None:
    res = client.post(
        "/chat", json=chat("llama3.1", "hello there"), headers=as_core_api(**{"X-Request-ID": "r1"})
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")
    events = sse_events(res.text)
    assert "".join(e.get("delta", "") for e in events) == "answer to: hello there"
    assert events[-1] == {
        "done": True,
        "model": "llama3.1",
        "usage": {"tokens_in": None, "tokens_out": None},
    }

    [row] = audit_rows(db_url)
    assert row == {
        "actor": "alice",
        "workspace_id": WORKSPACE,
        "action": "model.chat",
        "model": "llama3.1",
        "egress": False,
        "request_id": "r1",
        "detail": {"service": "core-api", "provider": "ollama"},
    }
    # The audit log records that a call happened, never what was said.
    assert "hello there" not in json.dumps(row)


def test_a_failure_mid_answer_arrives_in_band(gateway) -> None:
    with TestClient(gateway(llms={"ollama": BrokenStream()})) as c:
        res = c.post("/chat", json=chat("llama3.1"), headers=as_core_api())
    events = sse_events(res.text)
    assert events == [
        {"delta": "partial "},
        {"error": {"code": "upstream_unavailable", "message": "Ollama unreachable"}},
    ]


def test_an_unconfigured_provider_is_refused_without_a_call(gateway, db_url) -> None:
    with TestClient(gateway(sovereign=False, llms={})) as c:
        res = c.post("/chat", json=chat("openai/gpt-4o"), headers=as_core_api())
    assert res.status_code == 400
    assert "not configured" in res.json()["error"]["message"]
    assert audit_rows(db_url) == []


# ---------------------------------------------------------------- embed


def test_embeds_and_audits_counts_not_text(client, db_url) -> None:
    res = client.post(
        "/embed",
        json={"texts": ["confidential plan", "b"], "model": "nomic-embed-text"},
        headers=as_core_api(user=None, workspace=None),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert (len(body["embeddings"]), body["dimension"], body["model"]) == (
        2,
        768,
        "nomic-embed-text",
    )
    [row] = audit_rows(db_url)
    assert (row["actor"], row["action"], row["egress"]) == (
        "service:core-api",
        "model.embed",
        False,
    )
    assert row["detail"] == {"service": "core-api", "texts": 2}
    assert "confidential" not in json.dumps(row)


def test_embed_refuses_bad_batches(gateway, ollama, db_url) -> None:
    with TestClient(gateway(EMBED_MAX_TEXTS=4)) as c:
        for body in (
            {"texts": []},
            {"texts": ["x"] * 5},
            {"texts": ["x"], "model": "all-minilm"},
        ):
            res = c.post("/embed", json=body, headers=as_worker())
            assert res.status_code == 400, (body, res.text)
        assert c.post("/embed", json={"texts": ["x"] * 4}, headers=as_worker()).status_code == 200
    assert [p for p in model_calls(ollama)] == ["/api/embeddings"] * 4
    assert len(audit_rows(db_url)) == 1


# ------------------------------------------------------------ fail closed


def test_no_model_call_when_the_audit_log_is_down(gateway, ollama) -> None:
    audit = FailingAudit()
    with TestClient(gateway(audit=audit)) as c:
        res = c.post("/chat", json=chat("llama3.1"), headers=as_core_api())
        assert res.status_code == 503, res.text
        assert res.json()["error"]["code"] == "upstream_unavailable"
        assert "no model call was made" in res.json()["error"]["message"]

        assert c.post("/embed", json={"texts": ["a"]}, headers=as_worker()).status_code == 503

        # A refusal still stands when it cannot be recorded.
        assert c.post("/chat", json=chat("openai/gpt-4o"), headers=as_core_api()).status_code == 403
    assert audit.attempts == 3
    assert model_calls(ollama) == []


# ------------------------------------------------------------- end to end


def test_core_api_clients_speak_the_gateway_protocol(gateway, db_url) -> None:
    """core-api's real clients against the real gateway app, over ASGI."""
    app = gateway()
    workspace = uuid.UUID(WORKSPACE)

    async def run():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            models = GatewayModelClient("http://gateway", CORE_TOKEN, transport=transport)
            embedder = GatewayEmbedder(
                "http://gateway",
                WORKER_TOKEN,
                model="nomic-embed-text",
                dimension=768,
                transport=transport,
            )
            try:
                listed = await models.models()
                events = [
                    e
                    async for e in models.stream_chat(
                        [ChatMessage("system", "Be brief."), ChatMessage("user", "ping")],
                        model="llama3.1",
                        caller=OnBehalfOf("alice", workspace),
                    )
                ]
                vectors = await embedder.embed(["one", "two", "three"])
                with pytest.raises(ServiceError) as refused:
                    async for _ in models.stream_chat(
                        [ChatMessage("user", "ping")],
                        model="openai/gpt-4o",
                        caller=OnBehalfOf("alice", workspace),
                    ):
                        pass
                with pytest.raises(ServiceError) as missing:
                    async for _ in models.stream_chat(
                        [ChatMessage("user", "ping")],
                        model="not-pulled",
                        caller=OnBehalfOf("alice", workspace),
                    ):
                        pass
            finally:
                await models.aclose()
                await embedder.aclose()
        return listed, events, vectors, refused.value, missing.value

    listed, events, vectors, refused, missing = asyncio.run(run())

    assert listed == ["llama3.1"]
    assert "".join(e.text for e in events if isinstance(e, Delta)) == "chat answer to: ping"
    assert events[-1] == Done(model="llama3.1", tokens_in=None, tokens_out=None)
    assert [len(v) for v in vectors] == [768, 768, 768]
    assert refused.code is ErrorCode.FORBIDDEN
    assert "Sovereign mode" in refused.message
    # An unknown local model is an upstream failure, reported in-band.
    assert missing.code is ErrorCode.UPSTREAM_ERROR

    assert [(r["action"], r["actor"], r["egress"]) for r in audit_rows(db_url)] == [
        ("model.chat", "alice", False),
        ("model.embed", "service:ingest-worker", False),
        ("model.denied", "alice", False),
        ("model.chat", "alice", False),
    ]
