"""Sanity checks on the port definitions themselves.

Behavioural conformance is what the per-port contract suites prove (#10);
these only pin the shapes that the rest of v2 builds on.
"""

import dataclasses
from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest

from ldk_core import ports
from ldk_core.ports import (
    ChatMessage,
    CompletionRequest,
    LLMProvider,
    LoadedDocument,
    Page,
    Principal,
    SearchScope,
    Tool,
)


class _EchoProvider:
    name = "echo"

    async def list_models(self) -> list[str]:
        return ["echo-1"]

    async def complete(self, request: CompletionRequest) -> str:
        return request.messages[-1].content

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        for word in request.messages[-1].content.split():
            yield word


class _NotAProvider:
    name = "nope"

    async def list_models(self) -> list[str]:
        return []


class _UpperTool:
    name = "upper"
    description = "Upper-cases text."
    input_schema: Mapping[str, Any] = {"type": "object", "properties": {"text": {"type": "string"}}}

    async def invoke(self, arguments: Mapping[str, Any], *, principal: Principal | None) -> Any:
        return str(arguments["text"]).upper()


def test_runtime_checks_accept_a_complete_implementation() -> None:
    assert isinstance(_EchoProvider(), LLMProvider)
    assert isinstance(_UpperTool(), Tool)


def test_runtime_checks_reject_a_partial_one() -> None:
    assert not isinstance(_NotAProvider(), LLMProvider)


def test_every_port_is_runtime_checkable() -> None:
    names = ["AuthProvider", "Chunker", "DocumentLoader", "Embedder", "LLMProvider"]
    names += ["RateLimiter", "StorageBackend", "Tool", "VectorStore"]
    for name in names:
        port = getattr(ports, name)
        assert getattr(port, "_is_runtime_protocol", False), name
    assert len(names) == 9


def test_value_types_are_immutable() -> None:
    message = ChatMessage(role="user", content="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        message.content = "changed"  # type: ignore[misc]


def test_api_key_never_appears_in_repr() -> None:
    request = CompletionRequest(
        model="gpt-4o", messages=[ChatMessage("user", "hi")], api_key="sk-secret"
    )
    assert "sk-secret" not in repr(request)


def test_loaded_document_text_skips_empty_pages() -> None:
    doc = LoadedDocument(pages=[Page(1, "first"), Page(2, ""), Page(3, "third")])
    assert doc.text == "first\nthird"


def test_principal_roles() -> None:
    admin = Principal(subject="u1", kind="user", roles=frozenset({"admin"}))
    assert admin.has_role("admin")
    assert not admin.has_role("viewer")


def test_search_scope_is_hashable_for_cache_keys() -> None:
    a = SearchScope(collection_ids=frozenset({"c1", "c2"}), user_id="u1")
    b = SearchScope(collection_ids=frozenset({"c2", "c1"}), user_id="u1")
    assert hash(a) == hash(b)
    assert a == b
