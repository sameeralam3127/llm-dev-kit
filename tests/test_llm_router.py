from llm_service.providers.router import split_model


def test_plain_model_routes_to_ollama():
    assert split_model("llama3.1") == ("ollama", "llama3.1")


def test_openai_prefix_routes_to_openai():
    assert split_model("openai/gpt-4o") == ("openai", "gpt-4o")


def test_anthropic_prefix_routes_to_anthropic():
    assert split_model("anthropic/claude-sonnet-5") == ("anthropic", "claude-sonnet-5")


def test_unknown_prefix_stays_ollama():
    assert split_model("library/llama3.1") == ("ollama", "library/llama3.1")


def test_bare_prefix_stays_ollama():
    assert split_model("openai/") == ("ollama", "openai/")
