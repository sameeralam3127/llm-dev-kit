from app.services.cache import make_key


def test_make_key_is_stable_for_prompt_and_model():
    assert make_key("  hello  ", "llama3.1") == make_key("hello", "llama3.1")


def test_make_key_changes_by_model():
    assert make_key("hello", "model-a") != make_key("hello", "model-b")
