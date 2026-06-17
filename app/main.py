import os

import requests
import streamlit as st

from app.config import get_settings


settings = get_settings()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")

st.set_page_config(page_title=settings.app_name, page_icon="AI", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #f7f8fb; }
    [data-testid="stSidebar"] { background: #111827; color: #f9fafb; }
    [data-testid="stSidebar"] * { color: inherit; }
    .block-container { max-width: 1120px; padding-top: 2rem; }
    .status-pill {
        border: 1px solid #d1d5db;
        border-radius: 999px;
        color: #374151;
        display: inline-flex;
        font-size: .85rem;
        gap: .4rem;
        margin-bottom: 1rem;
        padding: .25rem .7rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_get(path: str, fallback):
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception:
        return fallback


def api_chat(message: str, model: str) -> dict:
    response = requests.post(
        f"{API_BASE_URL}/chat",
        json={"message": message, "model": model},
        timeout=90,
    )
    response.raise_for_status()
    return response.json()


def api_ingest_pdf(uploaded_file) -> int:
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
    response = requests.post(f"{API_BASE_URL}/ingest/pdf", files=files, timeout=120)
    response.raise_for_status()
    return int(response.json()["chunks"])


if "messages" not in st.session_state:
    st.session_state.messages = []

health = api_get("/health", {"status": "offline", "ollama_models": 0})
models = api_get("/models", [])
model_options = models or [settings.default_chat_model]

with st.sidebar:
    st.title(settings.app_name)
    st.caption("Local AI chat with RAG, cache, API, and MCP hooks.")
    st.divider()

    model = st.selectbox("Model", model_options)
    st.metric("Ollama models", health.get("ollama_models", 0))
    st.caption(f"API: {health.get('status', 'offline')}")

    st.divider()
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
    if uploaded_file and st.button("Index PDF", type="primary", use_container_width=True):
        try:
            with st.spinner("Indexing document"):
                chunks = api_ingest_pdf(uploaded_file)
            st.success(f"Indexed {chunks} chunks")
        except Exception as exc:
            st.error(f"Failed to process PDF: {exc}")

    st.divider()
    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.markdown('<span class="status-pill">Local-first AI workspace</span>', unsafe_allow_html=True)
st.title("AI Chat")
st.caption("Ask directly or upload PDFs to switch into retrieval-augmented answers.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask anything about your local knowledge base")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking"):
            try:
                result = api_chat(user_input, model=model)
                response = result["response"]
                if result.get("cached"):
                    st.caption("Cache hit")
            except Exception as exc:
                response = f"Error: {exc}"

            st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
