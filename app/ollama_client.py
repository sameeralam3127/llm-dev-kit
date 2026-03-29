import requests
import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def generate(prompt, model="llama3"):
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]


def embed(text, model="nomic-embed-text"):
    response = requests.post(
        f"{OLLAMA_HOST}/api/embeddings",
        json={
            "model": model,
            "prompt": text
        }
    )
    return response.json()["embedding"]