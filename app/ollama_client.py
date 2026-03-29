import requests
import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST")

def generate(prompt, model="llama3"):
    res = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": model, "prompt": prompt}
    )
    return res.json()["response"]