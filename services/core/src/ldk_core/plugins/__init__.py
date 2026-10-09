"""Plugin manifests, entry-point discovery and the registry.

Signature verification (``signing.py``) arrives with the marketplace in
Phase 8; until then ``PluginManifest.signature`` is carried but not checked.
"""

from ldk_core.plugins.discovery import (
    ENTRY_POINT_GROUP,
    DiscoveryFailure,
    DiscoveryResult,
    discover,
)
from ldk_core.plugins.kinds import (
    AUTH,
    CHUNKER,
    EMBEDDER,
    LLM,
    LOADER,
    PORT_BY_KIND,
    RATE_LIMITER,
    STORAGE,
    TOOL,
    VECTOR_STORE,
    PortSpec,
)
from ldk_core.plugins.manifest import (
    MANIFEST_FILENAME,
    ManifestError,
    Permission,
    Plugin,
    PluginKind,
    PluginManifest,
    load_manifest,
    parse_manifest,
)
from ldk_core.plugins.registry import (
    PluginConflictError,
    PluginContractError,
    PluginDisabledError,
    PluginError,
    PluginNotFoundError,
    PluginRegistry,
)

__all__ = [
    "AUTH",
    "CHUNKER",
    "EMBEDDER",
    "ENTRY_POINT_GROUP",
    "LLM",
    "LOADER",
    "MANIFEST_FILENAME",
    "PORT_BY_KIND",
    "RATE_LIMITER",
    "STORAGE",
    "TOOL",
    "VECTOR_STORE",
    "DiscoveryFailure",
    "DiscoveryResult",
    "ManifestError",
    "Permission",
    "Plugin",
    "PluginConflictError",
    "PluginContractError",
    "PluginDisabledError",
    "PluginError",
    "PluginKind",
    "PluginManifest",
    "PluginNotFoundError",
    "PluginRegistry",
    "PortSpec",
    "discover",
    "load_manifest",
    "parse_manifest",
]
