"""``Tool``: a callable capability exposed over MCP.

Replaces the hard-coded ``@mcp.tool()`` functions in ``mcp_service``; the MCP
server lists whatever the registry holds.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from ldk_core.ports.auth import Principal


@runtime_checkable
class Tool(Protocol):
    """One named operation with a JSON-Schema-described input."""

    @property
    def name(self) -> str:
        """Unique tool name as clients see it, e.g. ``"rag_search"``."""
        ...

    @property
    def description(self) -> str:
        """What the tool does, written for the model that will call it."""
        ...

    @property
    def input_schema(self) -> Mapping[str, Any]:
        """JSON Schema (draft 2020-12) for ``arguments``."""
        ...

    async def invoke(self, arguments: Mapping[str, Any], *, principal: Principal | None) -> Any:
        """Run the tool with already-validated arguments.

        Args:
            arguments: Input matching :attr:`input_schema`.
            principal: The caller, so the tool can apply the caller's access
                (e.g. search only their documents). ``None`` only in tests.

        Returns:
            A JSON-serialisable result.

        Raises:
            ldk_core.errors.ServiceError: Any expected failure.
        """
        ...
