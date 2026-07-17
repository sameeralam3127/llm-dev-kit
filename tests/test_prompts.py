from rag_service.prompts import build_prompt


def test_build_prompt_with_context():
    prompt = build_prompt("What changed?", "Release notes")

    assert "Release notes" in prompt
    assert "What changed?" in prompt
    assert "provided context" in prompt


def test_build_prompt_without_context():
    prompt = build_prompt("Hello")

    assert "Hello" in prompt
    assert "Context:" not in prompt
