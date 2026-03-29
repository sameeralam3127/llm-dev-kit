import requests
import os
from functools import lru_cache

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

session = requests.Session()


# ------------------ MODEL HELPERS ------------------

def get_models():
    try:
        res = session.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        res.raise_for_status()

        data = res.json()
        models = [m["name"] for m in data.get("models", [])]

        if not models:
            print("⚠️ No models found in Ollama")
        return models

    except Exception as e:
        print(f"❌ Error fetching models: {e}")
        return []


def model_exists(model_name):
    models = get_models()
    return model_name in models


def get_embedding_model():
    models = get_models()
    for m in models:
        if "embed" in m:
            return m

    print("❌ No embedding model found in Ollama.")
    print("👉 Run: ollama pull nomic-embed-text")
    return None


# ------------------ EMBEDDINGS ------------------

@lru_cache(maxsize=512)
def embed(text, model=None):
    if not text or not text.strip():
        print("⚠️ Empty text received for embedding")
        return None

    if model is None:
        model = get_embedding_model()

    if not model:
        return None

    if not model_exists(model):
        print(f"❌ Embedding model '{model}' not found.")
        print("👉 Install with: ollama pull nomic-embed-text")
        return None

    try:
        res = session.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30
        )

        res.raise_for_status()
        data = res.json()

        embedding = data.get("embedding")

        if not embedding:
            print("❌ Empty embedding returned:", data)
            return None

        return tuple(embedding)  # for caching

    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        return None


# ------------------ GENERATION ------------------

def generate(prompt, model):
    if not prompt or not prompt.strip():
        return "⚠️ Empty prompt."

    if not model_exists(model):
        return f"❌ Model '{model}' not found. Check 'ollama list'."

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

        if "response" not in data:
            return f"❌ Ollama error: {data}"

        return data["response"]

    except Exception as e:
        return f"❌ Request failed: {str(e)}"