"""core-api → model-gateway → Ollama, in one process, against one real Postgres."""

import asyncio

import httpx
from gateway_helpers import CORE_TOKEN, audit_rows
from identity import Issuer

from core_api.adapters.gateway import GatewayEmbedder, GatewayModelClient
from core_api.config import Settings as CoreApiSettings
from core_api.main import create_app as create_core_api

PEPPER = "pepper-for-tests-only-0123456789abcdef"


def test_a_chat_through_core_api_is_audited_against_the_user_and_workspace(
    gateway, db_url, ollama
) -> None:
    issuer = Issuer()
    gateway_app = gateway()
    to_gateway = httpx.ASGITransport(app=gateway_app)
    core_api = create_core_api(
        CoreApiSettings(
            DATABASE_URL=db_url,
            API_KEY_PEPPER=PEPPER,
            MODEL_GATEWAY_TOKEN=CORE_TOKEN,
            LOG_FORMAT="console",
        ),
        sessions=issuer.provider(),
        embedder=GatewayEmbedder(
            "http://gateway",
            CORE_TOKEN,
            model="nomic-embed-text",
            dimension=768,
            transport=to_gateway,
        ),
        models=GatewayModelClient("http://gateway", CORE_TOKEN, transport=to_gateway),
    )
    alice = issuer.bearer("user", sub="alice")

    async def run():
        async with (
            gateway_app.router.lifespan_context(gateway_app),
            core_api.router.lifespan_context(core_api),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=core_api), base_url="http://core-api"
            ) as client,
        ):
            created = await client.post(
                "/api/v1/workspaces", json={"slug": "acme", "name": "Acme"}, headers=alice
            )
            assert created.status_code == 201, created.text
            ws = created.json()["data"]["id"]
            headers = {**alice, "X-Workspace-Id": ws, "X-Request-ID": "e2e-1"}
            answer = await client.post(
                "/v1/chat/completions",
                json={"model": "llama3.1", "messages": [{"role": "user", "content": "ping"}]},
                headers=headers,
            )
            refused = await client.post(
                "/v1/chat/completions",
                json={"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "ping"}]},
                headers=headers,
            )
            return ws, answer, refused

    ws, answer, refused = asyncio.run(run())

    assert answer.status_code == 200, answer.text
    # No documents yet, so core-api sends the bare question: Ollama's generate endpoint.
    assert answer.json()["choices"][0]["message"]["content"] == "answer to: ping"
    assert refused.json()["error"]["code"] == "forbidden"

    gateway_rows = [r for r in audit_rows(db_url) if r["action"].startswith("model.")]
    assert [(r["action"], r["actor"], r["workspace_id"], r["egress"]) for r in gateway_rows] == [
        ("model.embed", "service:core-api", None, False),
        ("model.chat", "alice", ws, False),
        ("model.embed", "service:core-api", None, False),
        ("model.denied", "alice", ws, False),
    ]
    # One request id ties core-api's work to the gateway's audit events.
    assert {r["request_id"] for r in gateway_rows} == {"e2e-1"}
    assert [p for p, _ in ollama.requests if p in ("/api/chat", "/api/generate")] == [
        "/api/generate"
    ]
