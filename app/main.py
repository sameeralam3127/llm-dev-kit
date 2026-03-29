import streamlit as st
from app.ollama_client import generate
from app.rag import rag_query, ingest_pdf

st.set_page_config(page_title="LLM Dev Kit", layout="wide")

st.title("LLM Dev Kit")

# Sidebar
mode = st.sidebar.selectbox("Mode", ["Chat", "RAG"])

model = st.sidebar.selectbox(
    "Model",
    ["llama3", "mistral", "phi3"]
)

uploaded_file = st.sidebar.file_uploader("Upload PDF")

if uploaded_file:
    chunks = ingest_pdf(uploaded_file)
    st.sidebar.success(f"Ingested {chunks} chunks")

# Chat
if "history" not in st.session_state:
    st.session_state.history = []

query = st.chat_input("Ask something...")

if query:
    if mode == "RAG":
        response = rag_query(query, model=model)
    else:
        response = generate(query, model=model)

    st.session_state.history.append(("user", query))
    st.session_state.history.append(("assistant", response))

for role, msg in st.session_state.history:
    st.chat_message(role).write(msg)