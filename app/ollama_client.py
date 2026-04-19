"""
Ollama Client Module
Handles all interactions with the Ollama API for LLM operations
"""
import requests
import os
from typing import List, Optional
from functools import lru_cache

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_TIMEOUT = 60

# Create a session for connection pooling
session = requests.Session()


def get_models() -> List[str]:
    """
    Fetch available models from Ollama
    
    Returns:
        List of model names
    """
    try:
        response = session.get(
            f"{OLLAMA_HOST}/api/tags",
            timeout=5
        )
        response.raise_for_status()
        models = response.json().get("models", [])
        return [model["name"] for model in models]
    except Exception as e:
        print(f"❌ Failed to fetch models: {e}")
        return []


def get_embedding_model() -> Optional[str]:
    """
    Find the first available embedding model
    
    Returns:
        Embedding model name or None
    """
    models = get_models()
    for model in models:
        if "embed" in model.lower():
            return model
    
    print("⚠️  No embedding model found")
    print("💡 Run: ollama pull nomic-embed-text")
    return None


@lru_cache(maxsize=1024)
def generate_embedding(text: str, model: Optional[str] = None) -> Optional[List[float]]:
    """
    Generate embeddings for text using Ollama
    
    Args:
        text: Input text to embed
        model: Embedding model name (auto-detected if None)
    
    Returns:
        List of floats representing the embedding vector
    """
    if not text or not text.strip():
        return None
    
    # Auto-detect embedding model if not provided
    if not model:
        model = get_embedding_model()
    
    if not model:
        return None
    
    try:
        response = session.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={
                "model": model,
                "prompt": text
            },
            timeout=30
        )
        response.raise_for_status()
        
        embedding = response.json().get("embedding")
        if not embedding:
            print("❌ Empty embedding returned")
            return None
        
        return list(embedding)
    
    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        return None


def generate_response(prompt: str, model: str, temperature: float = 0.7) -> str:
    """
    Generate text response using Ollama
    
    Args:
        prompt: Input prompt
        model: Model name to use
        temperature: Sampling temperature (0.0 to 1.0)
    
    Returns:
        Generated text response
    """
    if not prompt or not prompt.strip():
        return "⚠️  Empty prompt provided"
    
    try:
        response = session.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 2000
                }
            },
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("response", "❌ No response from model")
    
    except requests.exceptions.Timeout:
        return "❌ Request timed out. Try a shorter prompt or different model."
    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to Ollama. Make sure it's running (ollama serve)"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def chat_completion(
    message: str,
    model: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7
) -> str:
    """
    Chat completion using Ollama's chat API
    
    Args:
        message: User message
        model: Model name to use
        system_prompt: Optional system prompt
        temperature: Sampling temperature
    
    Returns:
        Model's response
    """
    if not message or not message.strip():
        return "⚠️  Empty message provided"
    
    try:
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add user message
        messages.append({
            "role": "user",
            "content": message
        })
        
        response = session.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 2000
                }
            },
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("message", {}).get("content", "❌ No response from model")
    
    except requests.exceptions.Timeout:
        return "❌ Request timed out. Try a shorter message or different model."
    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to Ollama. Make sure it's running (ollama serve)"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Made with Bob
