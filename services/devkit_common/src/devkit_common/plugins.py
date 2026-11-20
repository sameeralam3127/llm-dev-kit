"""What a service has installed, for the admin console."""

from typing import Any

from ldk_core.plugins import PluginRegistry


def plugin_inventory(registry: PluginRegistry) -> list[dict[str, Any]]:
    """One row per registered plugin: identity, state and declared permissions.

    Deliberately leaves out each plugin's configuration: it holds API keys and
    other secrets, and the console only needs to know what is installed.
    """
    return [
        {
            "kind": manifest.kind.value,
            "name": manifest.name,
            "version": manifest.version,
            "enabled": registry.is_enabled(manifest.kind, manifest.name),
            "description": manifest.description,
            "permissions": sorted(permission.value for permission in manifest.permissions),
        }
        for manifest in registry.manifests()
    ]
