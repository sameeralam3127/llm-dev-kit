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