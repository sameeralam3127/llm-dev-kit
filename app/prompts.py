def build_prompt(query, context=None):
    if context:
        return f"""
You are a helpful assistant. Answer ONLY from the provided context.

Context:
{context}

Question:
{query}
"""
    else:
        return f"""
You are a helpful assistant.

Question:
{query}
"""


def get_system_prompt(role="assistant"):
    """Get system prompts for different roles"""
    prompts = {
        "assistant": "You are a helpful AI assistant.",
        "code": "You are an expert programmer and code reviewer.",
        "analyst": "You are a data analyst expert.",
        "summarizer": "You are an expert at summarizing content.",
    }
    return prompts.get(role, prompts["assistant"])