"""Sovereign mode: nothing leaves the network, and the audit log proves it."""

import json
import os
import subprocess
import sys
import textwrap

from fastapi.testclient import TestClient
from gateway_helpers import (
    CLOUD_KEY,
    CORE_TOKEN,
    WORKER_TOKEN,
    WORKSPACE,
    as_core_api,
    audit_rows,
    chat,
    sse_events,
)

from model_gateway.config import Settings
from model_gateway.main import plugin_entry_points


def model_calls(ollama) -> list[str]:
    return [path for path, _ in ollama.requests if path in ("/api/chat", "/api/generate")]


def test_sovereign_mode_blocks_cloud_models_and_writes_no_egress_event(
    client, db_url, ollama, cloud
) -> None:
    for model in ("openai/gpt-4o", "anthropic/claude-sonnet-5", "gpt-oss:120b-cloud"):
        res = client.post(
            "/chat", json=chat(model), headers=as_core_api(**{"X-Request-ID": "req-sov-1"})
        )
        assert res.status_code == 403, res.text
        assert res.json()["error"]["code"] == "forbidden"
        assert "Sovereign mode" in res.json()["error"]["message"]

    # Nothing reached a model: not the cloud provider, not Ollama's cloud proxy.
    assert cloud.calls == []
    assert model_calls(ollama) == []

    rows = audit_rows(db_url)
    assert [r for r in rows if r["egress"]] == []
    assert [(r["action"], r["model"]) for r in rows] == [
        ("model.denied", "openai/gpt-4o"),
        ("model.denied", "anthropic/claude-sonnet-5"),
        ("model.denied", "gpt-oss:120b-cloud"),
    ]
    first = rows[0]
    assert first["actor"] == "alice"
    assert first["workspace_id"] == WORKSPACE
    assert first["request_id"] == "req-sov-1"
    assert first["detail"] == {
        "service": "core-api",
        "provider": "openai",
        "reason": "sovereign_mode",
    }


def test_sovereign_mode_lists_only_local_models(client) -> None:
    res = client.get("/models", headers=as_core_api())
    assert res.json() == {"models": ["llama3.1"]}
    assert client.get("/health").json()["sovereign_mode"] is True


def test_without_sovereign_mode_cloud_calls_are_audited_as_egress(
    gateway, db_url, ollama, cloud
) -> None:
    with TestClient(gateway(sovereign=False)) as c:
        assert c.get("/models", headers=as_core_api()).json() == {
            "models": ["llama3.1", "gpt-oss:120b-cloud", "openai/gpt-4o"]
        }
        res = c.post("/chat", json=chat("openai/gpt-4o"), headers=as_core_api())
        assert res.status_code == 200, res.text
        assert "".join(e.get("delta", "") for e in sse_events(res.text)) == "cloud answer"
        assert c.post("/chat", json=chat("llama3.1"), headers=as_core_api()).status_code == 200

    assert [r.model for r in cloud.calls] == ["gpt-4o"]
    assert [(r["action"], r["model"], r["egress"]) for r in audit_rows(db_url)] == [
        ("model.chat", "openai/gpt-4o", True),
        ("model.chat", "llama3.1", False),
    ]


def test_sovereign_mode_never_imports_a_cloud_client() -> None:
    """Importing LiteLLM fetches a file from GitHub, so it must not even be imported."""
    script = textwrap.dedent(
        """
        import json, sys
        from model_gateway.config import Settings
        from model_gateway.main import build_models

        settings = Settings(
            DATABASE_URL="postgresql://unused",
            CORE_API_TOKEN=sys.argv[1],
            INGEST_WORKER_TOKEN=sys.argv[2],
            OPENAI_API_KEY=sys.argv[3],
        )
        _, llms, embedder = build_models(settings)
        print(json.dumps({
            "llms": sorted(llms),
            "embedder": embedder.model,
            "imported": sorted(m for m in sys.modules if "litellm" in m),
        }))
        """
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    env.pop("SOVEREIGN_MODE", None)
    out = subprocess.run(
        [sys.executable, "-c", script, CORE_TOKEN, WORKER_TOKEN, CLOUD_KEY],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert json.loads(out.stdout.splitlines()[-1]) == {
        "llms": ["ollama"],
        "embedder": "nomic-embed-text",
        "imported": [],
    }


def test_cloud_plugins_load_only_when_allowed_and_keyed() -> None:
    def names(**env) -> set[str]:
        settings = Settings(
            DATABASE_URL="postgresql://unused",
            CORE_API_TOKEN=CORE_TOKEN,
            INGEST_WORKER_TOKEN=WORKER_TOKEN,
            **env,
        )
        return {ep.name for ep in plugin_entry_points(settings)}

    local = {"llm.ollama", "embedder.ollama"}
    assert names(OPENAI_API_KEY=CLOUD_KEY) == local
    assert names(SOVEREIGN_MODE=False) == local
    assert names(SOVEREIGN_MODE=False, OPENAI_API_KEY=CLOUD_KEY) == local | {"llm.openai"}
