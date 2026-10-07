import asyncio
import importlib
import json
import sys
import textwrap
from collections.abc import AsyncIterator, Mapping
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from ldk_core.plugins import (
    CHUNKER,
    LLM,
    PORT_BY_KIND,
    TOOL,
    ManifestError,
    Permission,
    Plugin,
    PluginConflictError,
    PluginContractError,
    PluginDisabledError,
    PluginKind,
    PluginManifest,
    PluginNotFoundError,
    PluginRegistry,
    load_manifest,
    parse_manifest,
)
from ldk_core.ports import CompletionRequest, LLMProvider


def _manifest(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "echo",
        "version": "1.0.0",
        "kind": "llm",
        "description": "Echoes the last message.",
    }
    return {**data, **overrides}


class Echo:
    def __init__(self, name: str = "echo", greeting: str = "echo") -> None:
        self.name = name
        self.greeting = greeting

    async def list_models(self) -> list[str]:
        return ["echo-1"]

    async def complete(self, request: CompletionRequest) -> str:
        return f"{self.greeting}: {request.messages[-1].content}"

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        yield await self.complete(request)


ECHO_SCHEMA = {
    "type": "object",
    "properties": {"greeting": {"type": "string", "minLength": 1}},
    "additionalProperties": False,
}


def _echo_plugin(**manifest: Any) -> Plugin:
    return Plugin(
        manifest=parse_manifest(_manifest(config_schema=ECHO_SCHEMA, **manifest)),
        factory=lambda config: Echo(greeting=config.get("greeting", "echo")),
    )


# --- manifest ---------------------------------------------------------------


def test_minimal_manifest_gets_safe_defaults() -> None:
    m = parse_manifest(_manifest())
    assert m.kind is PluginKind.LLM
    assert m.permissions == frozenset()
    assert m.config_schema == {"type": "object"}
    assert m.signature is None


def test_permissions_are_parsed() -> None:
    m = parse_manifest(_manifest(permissions=["network", "secrets"]))
    assert m.permissions == {Permission.NETWORK, Permission.SECRETS}


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"name": "Has Spaces"}, "name"),
        ({"name": "-leading"}, "name"),
        ({"version": "1.0"}, "version"),
        ({"version": "v1.0.0"}, "version"),
        ({"kind": "teleporter"}, "kind"),
        ({"description": ""}, "description"),
        ({"permissions": ["root"]}, "permissions"),
        ({"schema_version": 2}, "schema_version"),
        ({"surprise": True}, "surprise"),
        ({"config_schema": {"type": "array"}}, "config_schema"),
        ({"config_schema": {"type": "object", "minProperties": "two"}}, "config_schema"),
    ],
)
def test_invalid_manifests_are_rejected_with_the_field_named(
    override: dict[str, Any], field: str
) -> None:
    with pytest.raises(ManifestError) as info:
        parse_manifest(_manifest(**override), source="echo/llm-dev-kit-plugin.json")
    message = str(info.value)
    assert message.startswith("Invalid plugin manifest (echo/llm-dev-kit-plugin.json):")
    assert f"  - {field}" in message


def test_every_problem_is_reported_at_once() -> None:
    with pytest.raises(ManifestError) as info:
        parse_manifest({"name": "Bad Name", "version": "x"})
    message = str(info.value)
    for field in ("name", "version", "kind", "description"):
        assert f"  - {field}" in message


def test_semver_prerelease_and_build_are_accepted() -> None:
    assert parse_manifest(_manifest(version="2.0.0-rc.1+build.5")).version == "2.0.0-rc.1+build.5"


def test_manifest_is_immutable() -> None:
    m = parse_manifest(_manifest())
    with pytest.raises(Exception):  # noqa: B017 - pydantic's frozen error type
        m.name = "other"  # type: ignore[misc]


def test_config_validation_names_the_field() -> None:
    m = parse_manifest(_manifest(config_schema=ECHO_SCHEMA))
    m.validate_config({"greeting": "hi"})
    with pytest.raises(ManifestError, match=r"plugin 'echo' at greeting"):
        m.validate_config({"greeting": ""})
    with pytest.raises(ManifestError, match=r"at <root>"):
        m.validate_config({"unexpected": 1})


# --- load_manifest ----------------------------------------------------------


@pytest.fixture
def plugin_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A throwaway importable package; yields a writer for its manifest."""
    name = f"ldk_test_pkg_{abs(hash(tmp_path)) % 10**8}"
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    def write(content: str | None) -> str:
        if content is not None:
            (package / "llm-dev-kit-plugin.json").write_text(content)
        return name

    yield write
    sys.modules.pop(name, None)


def test_load_manifest_from_a_package(plugin_package) -> None:
    package = plugin_package(json.dumps(_manifest()))
    assert load_manifest(package).name == "echo"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "Plugin manifest not found"),
        ("{not json", "not valid JSON"),
        ("[1, 2]", "must be a JSON object"),
        (json.dumps(_manifest(version="nope")), "  - version"),
    ],
)
def test_load_manifest_failures_are_clear(plugin_package, content, message) -> None:
    package = plugin_package(content)
    with pytest.raises(ManifestError, match=message.replace("(", r"\(")):
        load_manifest(package)


def test_load_manifest_for_a_missing_package() -> None:
    with pytest.raises(ManifestError, match="not found"):
        load_manifest("ldk_no_such_package_anywhere")


# --- registry ---------------------------------------------------------------


def test_port_specs_cover_every_kind() -> None:
    assert set(PORT_BY_KIND) == set(PluginKind)


def test_get_builds_once_and_is_typed() -> None:
    registry = PluginRegistry()
    registry.register(_echo_plugin())
    provider: LLMProvider = registry.get(LLM, "echo")
    assert isinstance(provider, Echo)
    assert registry.get(LLM, "echo") is provider


def test_configuration_is_validated_and_rebuilds_the_instance() -> None:
    registry = PluginRegistry()
    registry.register(_echo_plugin())
    first = registry.get(LLM, "echo")
    registry.configure(PluginKind.LLM, "echo", {"greeting": "hi"})
    second = registry.get(LLM, "echo")
    assert second is not first
    assert isinstance(second, Echo) and second.greeting == "hi"
    with pytest.raises(ManifestError):
        registry.configure(PluginKind.LLM, "echo", {"greeting": 3})
    assert registry.get(LLM, "echo") is second


def test_unknown_plugin() -> None:
    with pytest.raises(PluginNotFoundError, match="No llm plugin named 'ghost'"):
        PluginRegistry().get(LLM, "ghost")


def test_same_name_is_fine_across_kinds_but_not_within_one() -> None:
    registry = PluginRegistry()
    registry.register(_echo_plugin())
    registry.register(Plugin(parse_manifest(_manifest(kind="tool")), factory=lambda _: object()))
    with pytest.raises(PluginConflictError, match="already registered"):
        registry.register(_echo_plugin(version="2.0.0"))


def test_disable_and_enable() -> None:
    registry = PluginRegistry()
    registry.register(_echo_plugin())
    instance = registry.get(LLM, "echo")
    registry.disable(PluginKind.LLM, "echo")
    assert not registry.is_enabled(PluginKind.LLM, "echo")
    assert registry.names(LLM) == []
    assert registry.names(LLM, enabled_only=False) == ["echo"]
    with pytest.raises(PluginDisabledError):
        registry.get(LLM, "echo")
    registry.enable(PluginKind.LLM, "echo")
    assert registry.get(LLM, "echo") is not instance


def test_registered_disabled() -> None:
    registry = PluginRegistry()
    registry.register(_echo_plugin(), enabled=False)
    with pytest.raises(PluginDisabledError):
        registry.get(LLM, "echo")


def test_factory_output_must_satisfy_the_port() -> None:
    registry = PluginRegistry()
    registry.register(Plugin(parse_manifest(_manifest()), factory=lambda _: object()))
    with pytest.raises(PluginContractError, match="does not implement LLMProvider"):
        registry.get(LLM, "echo")


def test_factory_output_name_must_match_the_manifest() -> None:
    registry = PluginRegistry()
    registry.register(Plugin(parse_manifest(_manifest()), factory=lambda _: Echo(name="other")))
    with pytest.raises(PluginContractError, match="named 'other'"):
        registry.get(LLM, "echo")


def test_get_all_and_manifests_are_sorted() -> None:
    registry = PluginRegistry()
    for name in ("zeta", "alpha"):
        registry.register(
            Plugin(parse_manifest(_manifest(name=name)), factory=lambda _, n=name: Echo(name=n))
        )
    registry.register(Plugin(parse_manifest(_manifest(kind="chunker")), factory=lambda _: None))
    assert [p.name for p in registry.get_all(LLM)] == ["alpha", "zeta"]
    assert [(m.kind.value, m.name) for m in registry.manifests()] == [
        ("chunker", "echo"),
        ("llm", "alpha"),
        ("llm", "zeta"),
    ]
    assert [m.name for m in registry.manifests(PluginKind.LLM)] == ["alpha", "zeta"]
    assert registry.names(CHUNKER) == ["echo"]
    assert registry.names(TOOL) == []


# --- discovery through real entry points -------------------------------------

PLUGIN_MODULE = textwrap.dedent(
    """
    from ldk_core.plugins import Plugin, parse_manifest

    class Upper:
        name = "upper"
        description = "Upper-case text."
        input_schema = {"type": "object"}

        async def invoke(self, arguments, *, principal):
            return str(arguments.get("text", "")).upper()

    plugin = Plugin(
        manifest=parse_manifest(
            {"name": "upper", "version": "0.1.0", "kind": "tool",
             "description": "Upper-case text."}
        ),
        factory=lambda config: Upper(),
    )
    not_a_plugin = 42
    """
)


def _example_eps() -> list[EntryPoint]:
    """The fake distribution's entry points, found the normal way.

    Real first-party plugins are installed in the dev environment too, so
    the tests look only at the distribution they installed.
    """
    return [
        ep
        for ep in entry_points(group="llm_dev_kit.plugins")
        if ep.dist is not None and ep.dist.name == "ldk-example-plugin"
    ]


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Install a fake distribution whose entry points are given per test."""

    def install(entry_points: Mapping[str, str]) -> None:
        (tmp_path / "ldk_example_plugin.py").write_text(PLUGIN_MODULE)
        dist = tmp_path / "ldk_example_plugin-0.1.0.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: ldk-example-plugin\nVersion: 0.1.0\n"
        )
        lines = "\n".join(f"{k} = {v}" for k, v in entry_points.items())
        (dist / "entry_points.txt").write_text(f"[llm_dev_kit.plugins]\n{lines}\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        importlib.invalidate_caches()

    yield install
    sys.modules.pop("ldk_example_plugin", None)


def test_entry_point_plugin_is_discovered_and_usable(installed) -> None:
    installed({"tool.upper": "ldk_example_plugin:plugin"})
    registry = PluginRegistry()
    result = registry.load_entry_points(eps=_example_eps())

    assert [p.manifest.name for p in result.plugins] == ["upper"]
    assert result.failures == []
    tool = registry.get(TOOL, "upper")
    assert asyncio.run(tool.invoke({"text": "hi"}, principal=None)) == "HI"


def test_bad_entry_points_are_reported_not_raised(installed) -> None:
    installed(
        {
            "tool.upper": "ldk_example_plugin:plugin",
            "missing": "ldk_no_such_module:plugin",
            "wrongtype": "ldk_example_plugin:not_a_plugin",
            "upper": "ldk_example_plugin:plugin",
        }
    )
    registry = PluginRegistry()
    with capture_logs() as logs:
        result = registry.load_entry_points(eps=_example_eps())

    assert [p.manifest.name for p in result.plugins] == ["upper"]
    reasons = {f.entry_point.split(" = ")[0]: f.error for f in result.failures}
    assert reasons["missing"].startswith("import failed: ModuleNotFoundError")
    assert reasons["wrongtype"] == "expected a Plugin, got int"
    assert "expected 'tool.upper'" in reasons["upper"]
    assert all(f.distribution == "ldk-example-plugin" for f in result.failures)
    skipped = [e for e in logs if e["event"] == "plugin skipped"]
    assert [e["log_level"] for e in skipped] == ["warning"] * 3
    assert {e["entry_point"].split(" = ")[0] for e in skipped} == set(reasons)


def test_entry_point_conflicting_with_a_registered_plugin(installed) -> None:
    installed({"tool.upper": "ldk_example_plugin:plugin"})
    registry = PluginRegistry()
    registry.register(
        Plugin(
            PluginManifest.model_validate(
                {"name": "upper", "version": "9.9.9", "kind": "tool", "description": "Local."}
            ),
            factory=lambda _: None,
        )
    )
    result = registry.load_entry_points(eps=_example_eps())
    assert result.plugins == []
    (failure,) = result.failures
    assert "already registered (version 9.9.9)" in failure.error


def test_aclose_closes_built_instances_and_survives_failures() -> None:
    closed: list[str] = []

    class Closing(Echo):
        async def aclose(self) -> None:
            if self.name == "bad":
                raise RuntimeError("socket already gone")
            closed.append(self.name)

    registry = PluginRegistry()
    for name in ("bad", "good", "unused"):
        registry.register(
            Plugin(parse_manifest(_manifest(name=name)), factory=lambda _, n=name: Closing(name=n))
        )
    registry.get(LLM, "bad")
    registry.get(LLM, "good")
    with capture_logs() as logs:
        asyncio.run(registry.aclose())
    assert closed == ["good"]
    assert [e["name"] for e in logs if e["event"] == "plugin close failed"] == ["bad"]
    # A later get builds a fresh instance.
    assert registry.get(LLM, "good") is not None
