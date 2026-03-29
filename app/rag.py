def rag_query(query):
    docs = retrieve(query)   # from chroma
    context = "\n".join(docs)

    prompt = f"""
Answer using context:
{context}

Question: {query}
"""
    return generate(prompt)