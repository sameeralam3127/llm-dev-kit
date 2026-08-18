def build_rag_prompt(query: str, context: str) -> str:
    return f"""You are a helpful AI assistant. Answer the question based ONLY on the provided context.

Context:
{context}

Question: {query}

Instructions:
- Answer based only on the context provided
- If the context doesn't contain relevant information, say so
- Be concise and accurate
- Cite specific parts of the context when possible

Answer:"""


def build_chat_prompt(query: str) -> str:
    return f"""You are a helpful AI assistant. Answer the following question.

Question: {query}

Answer:"""


def build_prompt(query: str, context: str | None = None) -> str:
    if context:
        return build_rag_prompt(query, context)
    return build_chat_prompt(query)
