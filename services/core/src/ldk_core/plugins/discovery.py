"""Find installed plugins through Python entry points.

A plugin distribution declares, in its ``pyproject.toml``::

    [project.entry-points."llm_dev_kit.plugins"]
    ollama = "ldk_plugin_ollama:plugin"

where ``plugin`` is a :class:`~ldk_core.plugins.manifest.Plugin`. Discovery
never raises for a single bad plugin: it reports the failure and moves on, so
one broken install cannot stop a service from starting.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points

from ldk_core.plugins.manifest import Plugin

ENTRY_POINT_GROUP = "llm_dev_kit.plugins"
"""Entry-point group every plugin registers under."""


@dataclass(frozen=True, slots=True)
class DiscoveryFailure:
    """One entry point that could not be loaded.

    Attributes:
        entry_point: ``name = value`` as declared, to find the culprit.
        distribution: Installing distribution, if known.
        error: Why it failed, safe to log.
    """

    entry_point: str
    distribution: str | None
    error: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Everything one discovery pass found."""

    plugins: list[Plugin] = field(default_factory=list)
    failures: list[DiscoveryFailure] = field(default_factory=list)


def discover(
    group: str = ENTRY_POINT_GROUP, *, eps: Iterable[EntryPoint] | None = None
) -> DiscoveryResult:
    """Load every plugin entry point in ``group``.

    Args:
        group: Entry-point group to scan.
        eps: Entry points to load instead of scanning installed
            distributions; for tests.

    Returns:
        The loaded plugins, plus a failure record for each entry point that
        did not import or did not resolve to a :class:`Plugin`.
    """
    result = DiscoveryResult()
    for ep in eps if eps is not None else entry_points(group=group):
        declared = f"{ep.name} = {ep.value}"
        dist = ep.dist.name if ep.dist is not None else None
        try:
            obj = ep.load()
        except Exception as exc:  # noqa: BLE001 - a plugin's import may raise anything
            result.failures.append(
                DiscoveryFailure(declared, dist, f"import failed: {type(exc).__name__}: {exc}")
            )
            continue
        if not isinstance(obj, Plugin):
            result.failures.append(
                DiscoveryFailure(declared, dist, f"expected a Plugin, got {type(obj).__name__}")
            )
            continue
        if obj.manifest.name != ep.name:
            result.failures.append(
                DiscoveryFailure(
                    declared,
                    dist,
                    f"entry point name '{ep.name}' does not match manifest name "
                    f"'{obj.manifest.name}'",
                )
            )
            continue
        result.plugins.append(obj)
    return result
