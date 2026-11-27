"""An in-process stand-in for the Ollama HTTP API, for httpx.MockTransport."""

import hashlib
import json
from typing import Any

import httpx

DIMENSIONS = {"nomic-embed-text": 768, "all-minilm": 384}


class FakeOllama:
    """Answers /api/tags, /api/generate, /api/chat, /api/embed and /api/embeddings.

    Records every request body so tests can assert what was sent. Set
    ``fail_embed_call`` to make that /api/embed call (1-based) answer 500.
    """

    def __init__(self, models: tuple[str, ...] = ("llama3.1",)) -> None:
        self.models = models
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.wrong_dimension = False
        self.down = False
        self.fail_embed_call: int | None = None
        self.embed_calls = 0

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        body = json.loads(request.content) if request.content else {}
        self.requests.append((request.url.path, body))
        path = request.url.path
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in self.models]})
        if path == "/api/embeddings":
            return self._embed(body)
        if path == "/api/embed":
            return self._embed_batch(body)
        if path in ("/api/generate", "/api/chat"):
            return self._generate(path, body)
        return httpx.Response(404, text="404 page not found")

    def _generate(self, path: str, body: dict[str, Any]) -> httpx.Response:
        if body["model"] not in self.models:
            return httpx.Response(404, json={"error": f"model '{body['model']}' not found"})
        if path == "/api/generate":
            answer = f"answer to: {body['prompt']}"
        else:
            answer = f"chat answer to: {body['messages'][-1]['content']}"
        key = "response" if path == "/api/generate" else "message"

        def piece(text: str, done: bool) -> dict[str, Any]:
            value: Any = text if key == "response" else {"role": "assistant", "content": text}
            return {key: value, "done": done}

        if not body.get("stream"):
            return httpx.Response(200, json=piece(answer, True))
        words = answer.split(" ")
        lines = [piece(w + (" " if i < len(words) - 1 else ""), False) for i, w in enumerate(words)]
        lines.append(piece("", True))
        return httpx.Response(200, text="\n".join(json.dumps(line) for line in lines) + "\n")

    def vector(self, model: str, text: str) -> list[float]:
        """The vector this fake gives ``text``: the same for both endpoints."""
        dimension = DIMENSIONS[model.split(":", 1)[0]] - (1 if self.wrong_dimension else 0)
        seed = hashlib.sha256(text.encode()).digest()
        return [seed[i % len(seed)] / 255 for i in range(dimension)]

    def _embed(self, body: dict[str, Any]) -> httpx.Response:
        model = body["model"].split(":", 1)[0]
        if model not in DIMENSIONS:
            return httpx.Response(404, json={"error": f"model '{model}' not found"})
        return httpx.Response(200, json={"embedding": self.vector(model, body["prompt"])})

    def _embed_batch(self, body: dict[str, Any]) -> httpx.Response:
        self.embed_calls += 1
        if self.embed_calls == self.fail_embed_call:
            return httpx.Response(500, json={"error": "model runner crashed"})
        model = body["model"].split(":", 1)[0]
        if model not in DIMENSIONS:
            return httpx.Response(404, json={"error": f"model '{model}' not found"})
        texts = body["input"] if isinstance(body["input"], list) else [body["input"]]
        return httpx.Response(
            200,
            json={"model": body["model"], "embeddings": [self.vector(model, t) for t in texts]},
        )
