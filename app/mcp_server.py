from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.services.ollama_client import get_models
from app.services.rag import hybrid_query


settings = get_settings()
mcp = FastMCP(settings.app_name)


@mcp.tool()
def list_ollama_models() -> list[str]:
    """List local Ollama models available to the LLM Dev Kit."""
    return get_models()


@mcp.tool()
def ask_llm_dev_kit(message: str, model: str | None = None) -> str:
    """Ask the local RAG-enabled assistant a question."""
    selected_model = model or settings.default_chat_model
    return hybrid_query(message, model=selected_model).response


if __name__ == "__main__":
    mcp.run()
