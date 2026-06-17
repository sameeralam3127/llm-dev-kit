from functools import lru_cache

import requests

from app.config import get_settings


settings = get_settings()
session = requests.Session()


def get_models() -> list[str]:
    try:
        res = session.get(f"{settings.ollama_host}/api/tags", timeout=5)
        res.raise_for_status()
        return [m["name"] for m in res.json().get("models", [])]
    except Exception as exc:
        print(f"Failed to fetch models: {exc}")
        return []


def model_exists(model: str) -> bool:
    return model in get_models()


def get_embedding_model() -> str | None:
    models = get_models()
    if settings.default_embedding_model in models:
        return settings.default_embedding_model

    for model in models:
        if "embed" in model:
            return model

    print(f"No embedding model found. Run: ollama pull {settings.default_embedding_model}")
    return None


@lru_cache(maxsize=512)
def embed(text: str, model: str | None = None) -> list[float] | None:
    if not text.strip():
        return None

    model = model or get_embedding_model()
    if not model:
        return None

    if not model_exists(model):
        print(f"Embedding model '{model}' not found")
        return None

    try:
        res = session.post(
            f"{settings.ollama_host}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30,
        )
        res.raise_for_status()
        embedding = res.json().get("embedding")
        return list(embedding) if embedding else None
    except Exception as exc:
        print(f"Embedding error: {exc}")
        return None


def generate(prompt: str, model: str | None = None) -> str:
    model = model or settings.default_chat_model
    if not prompt.strip():
        return "Empty prompt"

    if not model_exists(model):
        return f"Model '{model}' not found"

    try:
        res = session.post(
            f"{settings.ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 512},
            },
            timeout=settings.request_timeout_seconds,
        )
        res.raise_for_status()
        data = res.json()
        return data.get("response", f"Ollama error: {data}")
    except Exception as exc:
        return f"Request failed: {exc}"
