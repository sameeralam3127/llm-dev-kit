import streamlit as st
from ollama_client import generate, get_models
from rag import rag_query, ingest_pdf

# ------------------ PAGE CONFIG ------------------
st.set_page_config(
    page_title="LLM Dev Kit",
    page_icon="🧠",
    layout="wide"
)

# ------------------ SIDEBAR ------------------
with st.sidebar:
    st.title("⚙️ Settings")

    mode = st.radio("Mode", ["Chat", "RAG"])

    models = get_models()
    model = st.selectbox("Model", models)

    st.divider()

    st.subheader("📄 Upload PDF")
    uploaded_file = st.file_uploader("Drag & drop PDF", type=["pdf"])

    if uploaded_file:
        with st.spinner("Processing PDF..."):
            chunks = ingest_pdf(uploaded_file)
            st.success(f"Indexed {chunks} chunks")

    st.divider()

    # ✅ Clear Chat Button
    if st.button("🧹 Clear Chat"):
        st.session_state.messages = []
        st.success("Chat cleared")

# ------------------ MAIN UI ------------------
st.title("🧠 LLM Dev Kit")

st.caption("Local LLM + RAG playground powered by Ollama")

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
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):

            if mode == "RAG":
                response = rag_query(user_input, model=model)
            else:
                response = generate(user_input, model=model)

            st.markdown(response)

    # Save response
    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })