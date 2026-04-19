"""
LLM Dev Kit - Enterprise Streamlit Frontend
Professional chatbot interface with streaming and persistent history
"""
import streamlit as st
import sys
import os
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ollama_client import get_models
from rag import hybrid_query_stream
from rag import ingest_pdf, clear_all_documents
from cache import clear_cache, get_cache_stats
from vector_store import get_collection_stats

# Page configuration
st.set_page_config(
    page_title="LLM Dev Kit - Enterprise",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional UI
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 600;
        color: #1a1a1a;
        margin-bottom: 0.5rem;
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .stButton button {
        width: 100%;
        border-radius: 4px;
        font-weight: 500;
    }
    .processing-indicator {
        color: #666;
        font-style: italic;
        animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
</style>
""", unsafe_allow_html=True)

# Constants
HISTORY_FILE = "/app/data/chat_history.json"
UPLOAD_DIR = "/app/data/uploads"


def ensure_data_directories():
    """Create data directories if they don't exist"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def load_chat_history():
    """Load chat history from file"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading history: {e}")
    return []


def save_chat_history(messages):
    """Save chat history to file"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(messages, f, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")


def initialize_session_state():
    """Initialize session state variables"""
    ensure_data_directories()
    
    if "messages" not in st.session_state:
        st.session_state.messages = load_chat_history()
    
    if "model" not in st.session_state:
        st.session_state.model = None


def render_sidebar():
    """Render the sidebar with settings and controls"""
    with st.sidebar:
        st.title("Configuration")
        
        # Model selection
        st.subheader("Model Settings")
        models = get_models()
        
        if models:
            # Add a placeholder option
            model_options = ["-- Select a model --"] + models
            
            selected_model = st.selectbox(
                "Select Model",
                model_options,
                index=0,
                help="Choose the LLM model for responses"
            )
            
            # Only set model if user selected a valid one
            if selected_model != "-- Select a model --":
                st.session_state.model = selected_model
                st.success(f"Active: {selected_model}")
            else:
                st.session_state.model = None
                st.warning("Please select a model to start chatting")
        else:
            st.error("No models available")
            st.info("Run: ollama pull llama3.1:8b")
            st.session_state.model = None
        
        st.divider()
        
        # Document upload
        st.subheader("Document Management")
        uploaded_file = st.file_uploader(
            "Upload PDF Document",
            type=["pdf"],
            help="Upload documents for context-aware responses"
        )
        
        if uploaded_file:
            with st.spinner("Processing document..."):
                try:
                    chunks = ingest_pdf(uploaded_file)
                    st.success(f"Processed: {chunks} chunks indexed")
                    st.caption(f"File: {uploaded_file.name}")
                except Exception as e:
                    st.error(f"Processing failed: {str(e)}")
        
        st.divider()
        
        # System statistics
        st.subheader("System Status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            cache_stats = get_cache_stats()
            if cache_stats.get("status") == "connected":
                st.metric("Cache Keys", cache_stats.get("keys", 0))
            else:
                st.caption("Cache: Offline")
        
        with col2:
            vector_stats = get_collection_stats()
            if vector_stats.get("status") == "connected":
                st.metric("Documents", vector_stats.get("document_count", 0))
            else:
                st.caption("Vector DB: Offline")
        
        st.divider()
        
        # Action buttons
        st.subheader("Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.messages = []
                save_chat_history([])
                st.rerun()
        
        with col2:
            if st.button("Clear Cache", use_container_width=True):
                if clear_cache():
                    st.success("Cache cleared")
                    st.rerun()
                else:
                    st.error("Failed")
        
        if st.button("Clear Documents", use_container_width=True):
            if clear_all_documents():
                st.success("Documents cleared")
                st.rerun()
            else:
                st.error("Failed")
        
        st.divider()
        
        # Export history
        if st.session_state.messages:
            if st.button("Export History", use_container_width=True):
                history_json = json.dumps(
                    st.session_state.messages,
                    indent=2
                )
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                st.download_button(
                    "Download JSON",
                    history_json,
                    file_name=f"chat_history_{timestamp}.json",
                    mime="application/json",
                    use_container_width=True
                )


def render_chat_interface():
    """Render the main chat interface"""
    # Header
    st.markdown(
        '<div class="main-header">LLM Development Kit</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sub-header">Enterprise AI Assistant</div>',
        unsafe_allow_html=True
    )
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Enter your message..."):
        # Check if model is selected
        if not st.session_state.model:
            st.error("Please select a model first")
            return
        
        # Add user message
        user_message = {
            "role": "user",
            "content": prompt
        }
        st.session_state.messages.append(user_message)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate and display assistant response with streaming
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            status_placeholder = st.empty()
            full_response = ""
            
            try:
                # Show processing indicator
                status_placeholder.markdown(
                    '<p class="processing-indicator">Processing your request...</p>',
                    unsafe_allow_html=True
                )
                
                # Use hybrid query with streaming
                for chunk in hybrid_query_stream(prompt, st.session_state.model):
                    full_response += chunk
                    # Clear status and show response
                    status_placeholder.empty()
                    message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
                # Add assistant response
                assistant_message = {
                    "role": "assistant",
                    "content": full_response
                }
                st.session_state.messages.append(assistant_message)
                
                # Save history
                save_chat_history(st.session_state.messages)
            
            except Exception as e:
                status_placeholder.empty()
                error_msg = f"Error: {str(e)}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })


def main():
    """Main application entry point"""
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Render main chat interface
    render_chat_interface()


if __name__ == "__main__":
    main()

# Made with Bob
