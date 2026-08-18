CLOUD_PROVIDERS = ("openai", "gemini", "anthropic")


def split_model(model: str) -> tuple[str, str]:
    """Route a model id to a provider.

    "openai/gpt-4o" -> ("openai", "gpt-4o"), "gemini/gemini-2.5-flash" ->
    ("gemini", "gemini-2.5-flash"), "anthropic/claude-sonnet-5" ->
    ("anthropic", "claude-sonnet-5"), anything else -> local Ollama.
    """
    provider, sep, name = model.partition("/")
    if sep and provider in CLOUD_PROVIDERS and name:
        return provider, name
    return "ollama", model
