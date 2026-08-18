import hmac
import json
import logging
from contextlib import asynccontextmanager
from hashlib import sha256
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from devkit_common.config import get_settings
from devkit_common.events import DocsChangedEvent, DocumentEventType
from devkit_common.interfaces import EventBus
from devkit_common.kafka_bus import KafkaEventBus, ensure_topics

logger = logging.getLogger(__name__)

DOCUMENT_SUFFIXES = (".md", ".mdx")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.event_bus = KafkaEventBus.from_settings()
    try:
        await ensure_topics()
    except Exception as exc:
        logger.warning("Could not ensure Kafka topics (will rely on auto-create): %s", exc)
    yield
    await app.state.event_bus.close()


app = FastAPI(title="LLM Dev Kit — Webhook Service", version="0.2.0", lifespan=lifespan)


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def verify_signature(secret: str, body: bytes, signature: str | None) -> None:
    if not secret:
        logger.warning(
            "GITHUB_WEBHOOK_SECRET is not set; accepting webhook without verification"
        )
        return
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing GitHub webhook signature",
        )

    expected = "sha256=" + hmac.new(secret.encode(), body, sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub webhook signature",
        )


def is_document_path(path: str) -> bool:
    return path.lower().endswith(DOCUMENT_SUFFIXES)


def iter_changed_documents(payload: dict[str, Any]) -> list[DocsChangedEvent]:
    repo_data = payload.get("repository") or {}
    repo = repo_data.get("name")
    owner = (repo_data.get("owner") or {}).get("name") or (
        repo_data.get("owner") or {}
    ).get("login")
    branch = str(payload.get("ref", "refs/heads/main")).removeprefix("refs/heads/")
    head_commit = payload.get("after") or ""
    html_url = repo_data.get("html_url")

    if not repo:
        raise ValueError("Push payload is missing repository name")

    events: dict[tuple[str, DocumentEventType], DocsChangedEvent] = {}
    for commit in payload.get("commits", []):
        commit_sha = commit.get("id") or head_commit
        changes = [
            (DocumentEventType.ADDED, commit.get("added", [])),
            (DocumentEventType.MODIFIED, commit.get("modified", [])),
            (DocumentEventType.REMOVED, commit.get("removed", [])),
        ]
        for event_type, paths in changes:
            for path in paths:
                if not is_document_path(path):
                    continue
                url = f"{html_url}/blob/{branch}/{path}" if html_url else None
                events[(path, event_type)] = DocsChangedEvent(
                    repo=repo,
                    owner=owner,
                    branch=branch,
                    path=path,
                    commit=commit_sha,
                    event=event_type,
                    url=url,
                )
    return list(events.values())


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "webhook-service"}


@app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str | None = Header(default=None),
    event_bus: EventBus = Depends(get_event_bus),
) -> dict[str, int | str]:
    body = await request.body()
    settings = get_settings()
    verify_signature(settings.github_webhook_secret, body, x_hub_signature_256)

    if x_github_event != "push":
        return {"status": "ignored", "published": 0}

    try:
        payload = json.loads(body)
        changed_events = iter_changed_documents(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for event in changed_events:
        await event_bus.publish(
            settings.kafka_topic_docs_changed, event, key=event.path
        )

    return {"status": "accepted", "published": len(changed_events)}
