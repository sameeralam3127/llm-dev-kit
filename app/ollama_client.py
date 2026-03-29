import requests
import os
from functools import lru_cache

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
session = requests.Session()


# ------------------ MODELS ------------------

def get_models():
    try:
        res = session.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        res.raise_for_status()
        return [m["name"] for m in res.json().get("models", [])]
    except Exception as e:
        print(f"❌ Failed to fetch models: {e}")
        return []


def model_exists(model):
    return model in get_models()


def get_embedding_model():
    for m in get_models():
        if "embed" in m:
            return m

    print("❌ No embedding model found")
    print("👉 Run: ollama pull nomic-embed-text")
    return None


# ------------------ EMBEDDINGS ------------------

@lru_cache(maxsize=512)
def embed(text, model=None):
    if not text.strip():
        return None

    model = model or get_embedding_model()

    if not model:
        return None

    if not model_exists(model):
        print(f"❌ Embedding model '{model}' not found")
        return None

    try:
        res = session.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30
        )
        res.raise_for_status()

        embedding = res.json().get("embedding")

        if not embedding:
            print("❌ Empty embedding returned")
            return None

        return list(embedding)  # ✅ FIX (no tuple)

    except Exception as e:
        print(f"❌ Embedding error: {e}")
        return None


# ------------------ GENERATION ------------------

def generate(prompt, model):
    if not prompt.strip():
        return "⚠️ Empty prompt"

    if not model_exists(model):
        return f"❌ Model '{model}' not found"

    try:
        res = session.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 512
                }
            },
            timeout=60
        )

        res.raise_for_status()
        data = res.json()

        return data.get("response", f"❌ Ollama error: {data}")

    except Exception as e:
        return f"❌ Request failed: {e}"