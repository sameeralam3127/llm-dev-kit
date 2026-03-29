import streamlit as st

st.title("LLM Dev Kit")

mode = st.sidebar.selectbox("Mode", ["Chat", "RAG"])

query = st.chat_input("Ask something...")

if query:
    if mode == "RAG":
        response = rag_query(query)
    else:
        response = generate(query)

    st.chat_message("user").write(query)
    st.chat_message("assistant").write(response)