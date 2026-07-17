import hmac
import json
from hashlib import sha256

from fastapi.testclient import TestClient

from devkit_common.config import Settings
import webhook_service.main as webhook_module
from webhook_service.main import app, get_event_bus


class FakeEventBus:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, topic, event, key=None):
        self.events.append((topic, event, key))


def test_github_webhook_publishes_document_changes(monkeypatch):
    bus = FakeEventBus()
    monkeypatch.setattr(
        webhook_module,
        "get_settings",
        lambda: Settings(GITHUB_WEBHOOK_SECRET=""),
    )
    app.dependency_overrides[get_event_bus] = lambda: bus
    client = TestClient(app)

    payload = {
        "ref": "refs/heads/main",
        "after": "91bc431",
        "repository": {
            "name": "compute-central-docs",
            "html_url": "https://github.com/acme/compute-central-docs",
            "owner": {"login": "acme"},
        },
        "commits": [
            {
                "id": "91bc431",
                "added": ["docs/a.md", "src/app.py"],
                "modified": ["docs/b.mdx"],
                "removed": ["docs/c.md"],
            }
        ],
    }

    response = client.post(
        "/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "push"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 202
    assert response.json()["published"] == 3
    published = [event.event for _, event, _ in bus.events]
    assert published == ["added", "modified", "removed"]
    assert all(key == event.path for _, event, key in bus.events)


def test_github_webhook_rejects_bad_signature(monkeypatch):
    bus = FakeEventBus()
    monkeypatch.setattr(
        webhook_module,
        "get_settings",
        lambda: Settings(GITHUB_WEBHOOK_SECRET="secret"),
    )
    app.dependency_overrides[get_event_bus] = lambda: bus
    client = TestClient(app)
    body = json.dumps({"repository": {"name": "repo"}, "commits": []}).encode()
    valid = "sha256=" + hmac.new(b"secret", body, sha256).hexdigest()

    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": valid.replace("a", "b", 1),
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 401
