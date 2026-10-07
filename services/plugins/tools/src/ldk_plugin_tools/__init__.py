"""llm-dev-kit plugin: the built-in MCP tools.

``tool.list_models`` and ``tool.ask_llm_dev_kit`` are the two tools
mcp-service has always offered, now behind the :class:`~ldk_core.ports.Tool`
port. Names, descriptions and input schemas are unchanged, so existing MCP
clients see the same tools.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

import httpx

from ldk_core.errors import ErrorCode, ServiceError, code_for_status
from ldk_core.plugins import Plugin, load_manifest
from ldk_core.ports import Principal


class _HttpTool:
    """Shared HTTP plumbing; failures become ServiceErrors."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self._timeout, transport=self._transport
        ) as client:
            try:
                res = await client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                raise ServiceError(
                    ErrorCode.UPSTREAM_UNAVAILABLE, f"{self.base_url} unreachable: {exc}"
                ) from exc
        if res.is_error:
            raise ServiceError(
                code_for_status(res.status_code),
                f"{self.base_url}{path} returned {res.status_code}: {res.text[:200]}",
            )
        return res.json()


class ListModelsTool(_HttpTool):
    """List every model llm-service can serve."""

    name = "list_models"
    description = (
        "List all models available to the LLM Dev Kit (local Ollama + configured cloud providers)."
    )
    input_schema: Mapping[str, Any] = MappingProxyType(
        {"properties": {}, "title": "list_modelsArguments", "type": "object"}
    )
    output_schema: Mapping[str, Any] = MappingProxyType(
        {
            "properties": {
                "result": {"items": {"type": "string"}, "title": "Result", "type": "array"}
            },
            "required": ["result"],
            "title": "list_modelsOutput",
            "type": "object",
        }
    )

    def __init__(self, llm_service_url: str, **kwargs: Any) -> None:
        super().__init__(llm_service_url, **kwargs)

    async def invoke(self, arguments: Mapping[str, Any], *, principal: Principal | None) -> Any:
        """Return the model ids from llm-service ``/models``."""
        body = await self._request("GET", "/models")
        return list(body.get("models", []))


class AskTool(_HttpTool):
    """Ask the RAG-enabled assistant through rag-service ``/chat``."""

    name = "ask_llm_dev_kit"
    description = (
        "Ask the RAG-enabled assistant a question. Model may be a local Ollama model\n"
        '    or a cloud model like "openai/gpt-4o" or "anthropic/claude-sonnet-5".'
    )
    input_schema: Mapping[str, Any] = MappingProxyType(
        {
            "properties": {
                "message": {"title": "Message", "type": "string"},
                "model": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "default": None,
                    "title": "Model",
                },
            },
            "required": ["message"],
            "title": "ask_llm_dev_kitArguments",
            "type": "object",
        }
    )
    output_schema: Mapping[str, Any] = MappingProxyType(
        {
            "properties": {"result": {"title": "Result", "type": "string"}},
            "required": ["result"],
            "title": "ask_llm_dev_kitOutput",
            "type": "object",
        }
    )

    def __init__(self, rag_service_url: str, **kwargs: Any) -> None:
        super().__init__(rag_service_url, **kwargs)

    async def invoke(self, arguments: Mapping[str, Any], *, principal: Principal | None) -> Any:
        """Return the assistant's answer text."""
        body = await self._request(
            "POST",
            "/chat",
            json={"message": arguments["message"], "model": arguments.get("model")},
        )
        return str(body.get("response", ""))


def _list_models(config: Mapping[str, Any]) -> ListModelsTool:
    return ListModelsTool(
        config["llm_service_url"], timeout_seconds=config.get("timeout_seconds", 30)
    )


def _ask(config: Mapping[str, Any]) -> AskTool:
    return AskTool(config["rag_service_url"], timeout_seconds=config.get("timeout_seconds", 120))


list_models_plugin = Plugin(
    load_manifest(__name__, "manifests/tool.list_models.json"), _list_models
)
ask_plugin = Plugin(load_manifest(__name__, "manifests/tool.ask_llm_dev_kit.json"), _ask)

__all__ = ["AskTool", "ListModelsTool", "ask_plugin", "list_models_plugin"]
