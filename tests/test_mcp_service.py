"""mcp-service: the built-in tools as plugins, served by the low-level server.

The expected listings and results below were captured from the FastMCP
server this replaced, so these tests prove MCP clients see no change.
"""

import asyncio
import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

import mcp_service.main as main
from devkit_common.config import Settings
from ldk_core.plugins import TOOL
from ldk_core.testing.contracts import ToolContract
from ldk_plugin_tools import AskTool, ListModelsTool

FASTMCP_TOOLS = [
    {
        "name": "list_models",
        "description": (
            "List all models available to the LLM Dev Kit "
            "(local Ollama + configured cloud providers)."
        ),
        "inputSchema": {"properties": {}, "title": "list_modelsArguments", "type": "object"},
        "outputSchema": {
            "properties": {
                "result": {"items": {"type": "string"}, "title": "Result", "type": "array"}
            },
            "required": ["result"],
            "title": "list_modelsOutput",
            "type": "object",
        },
    },
    {
        "name": "ask_llm_dev_kit",
        "description": (
            "Ask the RAG-enabled assistant a question. Model may be a local Ollama model\n"
            '    or a cloud model like "openai/gpt-4o" or "anthropic/claude-sonnet-5".'
        ),
        "inputSchema": {
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
        },
        "outputSchema": {
            "properties": {"result": {"title": "Result", "type": "string"}},
            "required": ["result"],
            "title": "ask_llm_dev_kitOutput",
            "type": "object",
        },
    },
]


class Services:
    """llm-service and rag-service as seen by the tools."""

    def __init__(self) -> None:
        self.chats: list[dict[str, Any]] = []
        self.down = False

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        if request.url.path == "/models":
            return httpx.Response(200, json={"models": ["llama3.1", "openai/gpt-4o"]})
        if request.url.path == "/chat":
            self.chats.append(json.loads(request.content))
            return httpx.Response(200, json={"response": "hi there"})
        return httpx.Response(404)


@pytest.fixture
def services() -> Services:
    return Services()


def _tools(services: Services) -> list[Any]:
    transport = services.transport()
    return [
        ListModelsTool("http://llm.test", timeout_seconds=5, transport=transport),
        AskTool("http://rag.test", timeout_seconds=5, transport=transport),
    ]


class TestListModelsContract(ToolContract):
    @pytest.fixture
    def tool(self, services: Services) -> ListModelsTool:
        return _tools(services)[0]

    @pytest.fixture
    def valid_arguments(self) -> Mapping[str, Any]:
        return {}


class TestAskContract(ToolContract):
    @pytest.fixture
    def tool(self, services: Services) -> AskTool:
        return _tools(services)[1]

    @pytest.fixture
    def valid_arguments(self) -> Mapping[str, Any]:
        return {"message": "hello", "model": None}


async def _session_run(services: Services, fn):
    server = main.create_server("LLM Dev Kit", _tools(services))
    async with create_connected_server_and_client_session(server) as session:
        return await fn(session)


def test_tool_listing_is_unchanged(services: Services) -> None:
    async def list_tools(session):
        return (await session.list_tools()).tools

    tools = asyncio.run(_session_run(services, list_tools))
    assert [t.model_dump(exclude_none=True) for t in tools] == FASTMCP_TOOLS


def test_results_are_shaped_like_fastmcp(services: Services) -> None:
    async def call(session):
        models = await session.call_tool("list_models", {})
        answer = await session.call_tool("ask_llm_dev_kit", {"message": "hello"})
        return models, answer

    models, answer = asyncio.run(_session_run(services, call))
    assert [c.text for c in models.content] == ["llama3.1", "openai/gpt-4o"]
    assert models.structuredContent == {"result": ["llama3.1", "openai/gpt-4o"]}
    assert not models.isError
    assert [c.text for c in answer.content] == ["hi there"]
    assert answer.structuredContent == {"result": "hi there"}
    assert services.chats == [{"message": "hello", "model": None}]


def test_invalid_arguments_unknown_tools_and_outages_are_tool_errors(services: Services) -> None:
    async def calls(session):
        missing = await session.call_tool("ask_llm_dev_kit", {})
        unknown = await session.call_tool("nope", {})
        services.down = True
        down = await session.call_tool("list_models", {})
        return missing, unknown, down

    missing, unknown, down = asyncio.run(_session_run(services, calls))
    assert missing.isError and "message" in missing.content[0].text
    assert unknown.isError and "nope" in unknown.content[0].text
    assert down.isError and "unreachable" in down.content[0].text


def test_real_build_registry_configures_both_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_SERVICE_URL", "http://llm.test:8010")
    monkeypatch.setenv("RAG_SERVICE_URL", "http://rag.test:8020")
    registry = main.build_registry(Settings())
    tools = {t.name: t for t in registry.get_all(TOOL)}
    assert set(tools) == {"list_models", "ask_llm_dev_kit"}
    assert tools["list_models"].base_url == "http://llm.test:8010"
    assert tools["ask_llm_dev_kit"].base_url == "http://rag.test:8020"
