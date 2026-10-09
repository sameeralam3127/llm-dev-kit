from collections.abc import Collection

LOCAL_PROVIDER = "ollama"
CLOUD_PROVIDERS = ("openai", "gemini", "anthropic")


def split_model(model: str, cloud: Collection[str] = CLOUD_PROVIDERS) -> tuple[str, str]:
    """Route a model id to a provider.

    "openai/gpt-4o" -> ("openai", "gpt-4o"), "gemini/gemini-2.5-flash" ->
    ("gemini", "gemini-2.5-flash"), "anthropic/claude-sonnet-5" ->
    ("anthropic", "claude-sonnet-5"), anything else -> local Ollama.

    ``cloud`` is the set of prefixed providers; the service passes every
    enabled LLM plugin except the local one, so a new provider plugin is
    routable without touching this function.
    """
    provider, sep, name = model.partition("/")
    if sep and provider in cloud and name:
        return provider, name
    return LOCAL_PROVIDER, model
