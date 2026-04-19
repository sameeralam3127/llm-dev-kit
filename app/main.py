"""
LLM Dev Kit - Streamlit Frontend
Main application interface for local LLM with RAG capabilities
"""
import streamlit as st
from app.ollama_client import get_models
from app.rag import hybrid_query, ingest_pdf, clear_all_documents
from app.cache import clear_cache, get_cache_stats
from app.vector_store import get_collection_stats

# Page configuration
st.set_page_config(
    page_title="LLM Dev Kit",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .stAlert {
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "model" not in st.session_state:
        st.session_state.model = None


def render_sidebar():
    """Render the sidebar with settings and controls"""
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # Model selection
        st.subheader("Model Selection")
        models = get_models()
        
        if models:
            selected_model = st.selectbox(
                "Choose Model",
                models,
                index=0,
                help="Select the LLM model to use"
            )
            st.session_state.model = selected_model
        else:
            st.error("❌ No models found")
            st.info("Run: `ollama pull llama3.1`")
            st.session_state.model = None
        
        st.divider()
        
        # PDF Upload
        st.subheader("📄 Upload PDF")
        uploaded_file = st.file_uploader(
            "Upload a PDF document",
            type=["pdf"],
            help="Upload a PDF to enable RAG-based answers"
        )
        
        if uploaded_file:
            try:
                with st.spinner("🔄 Processing PDF..."):
                    chunks = ingest_pdf(uploaded_file)
                    st.success(f"✅ Indexed {chunks} chunks")
            except Exception as e:
                st.error(f"❌ Failed to process PDF: {e}")
        
        st.divider()
        
        # Statistics
        st.subheader("📊 Statistics")
        
        # Cache stats
        cache_stats = get_cache_stats()
        if cache_stats.get("status") == "connected":
            st.metric("Cache Keys", cache_stats.get("keys", 0))
            st.metric("Cache Hits", cache_stats.get("hits", 0))
        else:
            st.info("Cache: Unavailable")
        
        # Vector store stats
        vector_stats = get_collection_stats()
        if vector_stats.get("status") == "connected":
            st.metric("Documents", vector_stats.get("document_count", 0))
        else:
            st.info("Vector Store: Unavailable")
        
        st.divider()
        
        # Actions
        st.subheader("🔧 Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        
        with col2:
            if st.button("🧹 Clear Cache", use_container_width=True):
                if clear_cache():
                    st.success("Cache cleared!")
                else:
                    st.error("Failed to clear cache")
        
        if st.button("📚 Clear Documents", use_container_width=True):
            if clear_all_documents():
                st.success("Documents cleared!")
            else:
                st.error("Failed to clear documents")


def render_chat_interface():
    """Render the main chat interface"""
    # Header
    st.markdown('<div class="main-header">🤖 LLM Dev Kit</div>', 
                unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Local LLM with RAG • Powered by Ollama</div>',
        unsafe_allow_html=True
    )
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything..."):
        # Check if model is selected
        if not st.session_state.model:
            st.error("❌ Please select a model first")
            return
        
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                try:
                    response = hybrid_query(
                        prompt,
                        model=st.session_state.model
                    )
                    st.markdown(response)
                    
                    # Add assistant response to chat
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response
                    })
                
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })


def render_info_section():
    """Render information section at the bottom"""
    with st.expander("ℹ️ How to Use"):
        st.markdown("""
        ### Getting Started
        
        1. **Select a Model**: Choose an LLM model from the sidebar
        2. **Upload PDF (Optional)**: Upload documents for RAG-based answers
        3. **Ask Questions**: Type your question in the chat input
        
        ### Features
        
        - 🔍 **Hybrid Query**: Automatically uses RAG when relevant documents exist
        - 💾 **Caching**: Responses are cached for faster retrieval
        - 📄 **PDF Support**: Upload and query PDF documents
        - 🎯 **Local First**: Everything runs locally, no external APIs
        
        ### Tips
        
        - Upload PDFs to get context-aware answers
        - Clear cache if you want fresh responses
        - Use different models for different tasks
        """)


def main():
    """Main application entry point"""
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Render main chat interface
    render_chat_interface()
    
    # Render info section
    render_info_section()


if __name__ == "__main__":
    main()

# Made with Bob
