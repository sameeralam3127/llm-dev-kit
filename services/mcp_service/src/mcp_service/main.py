import httpx
from mcp.server.fastmcp import FastMCP

from devkit_common.config import get_settings

settings = get_settings()
mcp = FastMCP(settings.app_name)


@mcp.tool()
async def list_models() -> list[str]:
    """List all models available to the LLM Dev Kit (local Ollama + configured cloud providers)."""
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(f"{settings.llm_service_url}/models")
        res.raise_for_status()
        return res.json().get("models", [])


@mcp.tool()
async def ask_llm_dev_kit(message: str, model: str | None = None) -> str:
    """Ask the RAG-enabled assistant a question. Model may be a local Ollama model
    or a cloud model like "openai/gpt-4o" or "anthropic/claude-sonnet-5"."""
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        res = await client.post(
            f"{settings.rag_service_url}/chat",
            json={"message": message, "model": model},
        )
        res.raise_for_status()
        return res.json().get("response", "")


if __name__ == "__main__":
    mcp.run()
