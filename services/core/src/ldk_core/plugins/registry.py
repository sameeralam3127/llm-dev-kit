"""The plugin registry: the only place consumers get implementations from.

A service builds one registry at startup, fills it from entry points (and,
in tests, by registering plugins directly), applies configuration, then asks
for implementations by port and name::

    registry = PluginRegistry()
    registry.load_entry_points()
    registry.configure(PluginKind.LLM, "ollama", {"host": settings.ollama_host})
    provider = registry.get(LLM, "ollama")   # typed as LLMProvider

Enabled/disabled state and configuration live in memory for now; Phase 5
persists them in the ``rag.plugins`` table and Phase 7 edits them from the
admin dashboard.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Mapping
from importlib.metadata import EntryPoint
from typing import Any, TypeVar, cast

from ldk_core.observability.logging import get_logger
from ldk_core.plugins.discovery import (
    ENTRY_POINT_GROUP,
    DiscoveryFailure,
    DiscoveryResult,
    discover,
)
from ldk_core.plugins.kinds import PortSpec
from ldk_core.plugins.manifest import Plugin, PluginKind, PluginManifest

T = TypeVar("T")
_Key = tuple[PluginKind, str]

_log = get_logger(__name__)


class PluginError(Exception):
    """Base class for registry failures. Messages are safe to log and show."""


class PluginNotFoundError(PluginError, LookupError):
    """No plugin of that kind and name is registered."""


class PluginDisabledError(PluginError):
    """The plugin is registered but an admin has disabled it."""


class PluginConflictError(PluginError):
    """A plugin of the same kind and name is already registered."""


class PluginContractError(PluginError, TypeError):
    """A plugin's factory built something that does not satisfy its port."""


class PluginRegistry:
    """Holds plugins by kind and name, and builds their implementations lazily.

    Each implementation is built once, on first :meth:`get`, from the
    configuration last given to :meth:`configure` (an empty object if none),
    and reused after that. Reconfiguring or disabling a plugin discards the
    built instance.
    """

    def __init__(self) -> None:
        self._plugins: dict[_Key, Plugin] = {}
        self._enabled: dict[_Key, bool] = {}
        self._config: dict[_Key, Mapping[str, Any]] = {}
        self._instances: dict[_Key, object] = {}
        self._lock = threading.RLock()

    def register(self, plugin: Plugin, *, enabled: bool = True) -> None:
        """Add a plugin.

        Raises:
            PluginConflictError: Another plugin already has this kind and name.
        """
        key = _key(plugin.manifest)
        with self._lock:
            if key in self._plugins:
                existing = self._plugins[key].manifest
                raise PluginConflictError(
                    f"{key[0].value} plugin '{key[1]}' is already registered "
                    f"(version {existing.version})"
                )
            self._plugins[key] = plugin
            self._enabled[key] = enabled

    def load_entry_points(
        self, group: str = ENTRY_POINT_GROUP, *, eps: Iterable[EntryPoint] | None = None
    ) -> DiscoveryResult:
        """Discover installed plugins and register each one.

        A plugin that fails to load or conflicts with one already registered
        is skipped and reported, never raised, so one bad install cannot stop
        the service. Every failure is also logged as a warning.

        Args:
            group: Entry-point group to scan.
            eps: Explicit entry points instead of a scan; for tests.

        Returns:
            What was registered and what was skipped, with reasons.
        """
        found = discover(group, eps=eps)
        result = DiscoveryResult(failures=list(found.failures))
        for plugin in found.plugins:
            try:
                self.register(plugin)
            except PluginConflictError as exc:
                result.failures.append(DiscoveryFailure(plugin.manifest.name, None, str(exc)))
            else:
                result.plugins.append(plugin)
        for failure in result.failures:
            _log.warning(
                "plugin skipped",
                entry_point=failure.entry_point,
                distribution=failure.distribution,
                reason=failure.error,
            )
        return result

    def configure(self, kind: PluginKind, name: str, config: Mapping[str, Any]) -> None:
        """Set a plugin's configuration, validating it against its schema now.

        Raises:
            PluginNotFoundError: No such plugin.
            ldk_core.plugins.manifest.ManifestError: ``config`` violates the
                plugin's ``config_schema``.
        """
        with self._lock:
            plugin = self._require((kind, name))
            plugin.manifest.validate_config(config)
            self._config[(kind, name)] = dict(config)
            self._instances.pop((kind, name), None)

    def enable(self, kind: PluginKind, name: str) -> None:
        """Allow :meth:`get` to return this plugin."""
        with self._lock:
            self._require((kind, name))
            self._enabled[(kind, name)] = True

    def disable(self, kind: PluginKind, name: str) -> None:
        """Stop :meth:`get` from returning this plugin and drop its instance."""
        with self._lock:
            self._require((kind, name))
            self._enabled[(kind, name)] = False
            self._instances.pop((kind, name), None)

    def is_enabled(self, kind: PluginKind, name: str) -> bool:
        """Return whether the plugin is registered and enabled."""
        return self._enabled.get((kind, name), False)

    def manifests(self, kind: PluginKind | None = None) -> list[PluginManifest]:
        """List registered manifests, enabled or not, sorted by kind then name."""
        return [
            plugin.manifest
            for key, plugin in sorted(self._plugins.items())
            if kind is None or key[0] is kind
        ]

    def names(self, spec: PortSpec[Any], *, enabled_only: bool = True) -> list[str]:
        """List plugin names for one port, sorted."""
        return sorted(
            name
            for (kind, name) in self._plugins
            if kind is spec.kind and (not enabled_only or self._enabled[(kind, name)])
        )

    def get(self, spec: PortSpec[T], name: str) -> T:
        """Return the implementation of ``spec`` named ``name``, building it once.

        Raises:
            PluginNotFoundError: No such plugin.
            PluginDisabledError: It exists but is disabled.
            PluginContractError: Its factory built an object that does not
                satisfy the port, or whose ``name`` differs from the manifest.
        """
        key = (spec.kind, name)
        with self._lock:
            plugin = self._require(key)
            if not self._enabled[key]:
                raise PluginDisabledError(f"{spec.kind.value} plugin '{name}' is disabled")
            if key not in self._instances:
                self._instances[key] = self._build(spec, plugin)
            return cast(T, self._instances[key])

    def get_all(self, spec: PortSpec[T]) -> list[T]:
        """Return every enabled implementation of ``spec``, sorted by name."""
        return [self.get(spec, name) for name in self.names(spec)]

    def _build(self, spec: PortSpec[Any], plugin: Plugin) -> object:
        """Instantiate ``plugin`` and check the result against its port."""
        manifest = plugin.manifest
        config = self._config.get(_key(manifest), {})
        manifest.validate_config(config)
        instance = plugin.factory(config)
        if not isinstance(instance, spec.protocol):
            raise PluginContractError(
                f"{spec.kind.value} plugin '{manifest.name}' built a "
                f"{type(instance).__name__}, which does not implement "
                f"{spec.protocol.__name__}"
            )
        built_name = getattr(instance, "name", None)
        if built_name != manifest.name:
            raise PluginContractError(
                f"{spec.kind.value} plugin '{manifest.name}' built an instance named "
                f"{built_name!r}; it must match the manifest"
            )
        return instance

    def _require(self, key: _Key) -> Plugin:
        """Return the plugin for ``key`` or raise :class:`PluginNotFoundError`."""
        try:
            return self._plugins[key]
        except KeyError:
            raise PluginNotFoundError(f"No {key[0].value} plugin named '{key[1]}'") from None


def _key(manifest: PluginManifest) -> _Key:
    """Registry key for a manifest."""
    return (manifest.kind, manifest.name)
