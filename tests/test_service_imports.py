"""Each service's ASGI entry module must import cleanly.

Runtime deps are unpinned, so an upstream rename (mcp 2.x dropping FastMCP)
breaks a freshly built image at import time. This catches it in CI first.
"""

import importlib

import pytest


@pytest.mark.parametrize("module", ["llm_service.main", "rag_service.main", "mcp_service.main"])
def test_service_entry_module_imports(module: str) -> None:
    importlib.import_module(module)
