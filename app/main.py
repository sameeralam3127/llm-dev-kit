import streamlit as st
from ollama_client import get_models
from rag import hybrid_query, ingest_pdf

# ------------------ PAGE CONFIG ------------------
st.set_page_config(
    page_title="LLM Dev Kit",
    layout="wide"
)

# ------------------ SIDEBAR ------------------
with st.sidebar:
    st.title("Settings")

    models = get_models()
    model = st.selectbox("Model", models if models else ["No models found"])

    st.divider()

    st.subheader("Upload PDF")
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

    if uploaded_file:
        try:
            with st.spinner("Indexing document..."):
                chunks = ingest_pdf(uploaded_file)
                st.success(f"Indexed {chunks} chunks")
        except Exception as e:
            st.error(f"Failed to process PDF: {e}")

    st.divider()

    if st.button("Clear Chat"):
        st.session_state.messages = []

# ------------------ MAIN UI ------------------
st.title("LLM Dev Kit")
st.caption("Local LLM with hybrid retrieval (RAG + fallback)")

# ------------------ SESSION STATE ------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------ DISPLAY CHAT ------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ------------------ INPUT ------------------
user_input = st.chat_input("Ask something...")

if user_input:
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            try:
                response = hybrid_query(user_input, model=model)
            except Exception as e:
                response = f"Error: {str(e)}"

            st.markdown(response)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })