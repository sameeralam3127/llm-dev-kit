"""Plugin manifests: what a plugin is, and what it asks to be allowed to do.

A first-party plugin ships its manifest as ``llm-dev-kit-plugin.json`` next to
its code. That file is what Phase 8 signs and what an admin reads before
approving an install. :func:`load_manifest` reads and validates it.

Permissions are *disclosure*, not a sandbox: a plugin is in-process Python
and can do anything its host service can (decision D6, risk R4).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from typing import Any, Literal

import jsonschema
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MANIFEST_FILENAME = "llm-dev-kit-plugin.json"
"""File name of a plugin's manifest inside its package."""

_SEMVER = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class PluginKind(StrEnum):
    """Which port a plugin implements. One plugin, one kind."""

    LLM = "llm"
    EMBEDDER = "embedder"
    VECTOR_STORE = "vector_store"
    LOADER = "loader"
    CHUNKER = "chunker"
    AUTH = "auth"
    RATE_LIMITER = "rate_limiter"
    TOOL = "tool"
    STORAGE = "storage"


class Permission(StrEnum):
    """Capabilities a plugin declares it uses, shown to the approving admin."""

    NETWORK = "network"
    """Makes outbound connections (beyond the services it is configured with)."""
    FILESYSTEM = "filesystem"
    """Reads or writes files outside its own package."""
    SECRETS = "secrets"
    """Receives credentials through its configuration."""


class ManifestError(ValueError):
    """A manifest is missing, unreadable or invalid. The message says why."""


class PluginManifest(BaseModel):
    """Validated contents of ``llm-dev-kit-plugin.json``.

    Attributes:
        schema_version: Manifest format version; only ``1`` exists.
        name: Unique within its kind; lower-case letters, digits, ``_`` and
            ``-``. Also the model-id prefix for LLM providers.
        version: Semantic version of the plugin.
        kind: The port it implements.
        description: One or two sentences for the admin UI.
        permissions: What the plugin declares it does; see :class:`Permission`.
        config_schema: JSON Schema (draft 2020-12) for the plugin's
            configuration object. Defaults to an object with no rules.
        signature: Detached signature over the manifest and wheel, verified
            in Phase 8. Unused until then.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,62}$")
    version: str = Field(pattern=_SEMVER)
    kind: PluginKind
    description: str = Field(min_length=1, max_length=500)
    permissions: frozenset[Permission] = frozenset()
    config_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    signature: str | None = None

    @field_validator("config_schema")
    @classmethod
    def _schema_describes_an_object(cls, schema: dict[str, Any]) -> dict[str, Any]:
        """Reject a config schema that is not a valid JSON Schema for an object."""
        try:
            jsonschema.Draft202012Validator.check_schema(schema)
        except jsonschema.SchemaError as exc:
            raise ValueError(f"config_schema is not valid JSON Schema: {exc.message}") from None
        if schema.get("type") != "object":
            raise ValueError('config_schema must have "type": "object"')
        return schema

    def validate_config(self, config: Mapping[str, Any]) -> None:
        """Check ``config`` against :attr:`config_schema`.

        Raises:
            ManifestError: Naming the first offending field.
        """
        validator = jsonschema.Draft202012Validator(self.config_schema)
        error = jsonschema.exceptions.best_match(validator.iter_errors(dict(config)))
        if error is not None:
            where = "/".join(str(p) for p in error.absolute_path) or "<root>"
            raise ManifestError(
                f"Invalid config for plugin '{self.name}' at {where}: {error.message}"
            )


@dataclass(frozen=True, slots=True)
class Plugin:
    """What a plugin's entry point resolves to.

    Attributes:
        manifest: The plugin's validated manifest.
        factory: Builds the implementation from a config that has already
            been validated against ``manifest.config_schema``.
    """

    manifest: PluginManifest
    factory: Callable[[Mapping[str, Any]], object]


def parse_manifest(data: Mapping[str, Any], *, source: str = "manifest") -> PluginManifest:
    """Validate manifest data, turning pydantic's errors into one readable message.

    Args:
        data: The decoded JSON object.
        source: Where it came from, for the error message.

    Raises:
        ManifestError: Listing every problem.
    """
    try:
        return PluginManifest.model_validate(data)
    except ValidationError as exc:
        problems = "\n".join(
            f"  - {'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors(include_url=False)
        )
        raise ManifestError(f"Invalid plugin manifest ({source}):\n{problems}") from None


def load_manifest(package: str, filename: str = MANIFEST_FILENAME) -> PluginManifest:
    """Read and validate the manifest file shipped inside ``package``.

    Args:
        package: Dotted name of the plugin's package, usually ``__package__``.
        filename: Manifest file name inside the package.

    Raises:
        ManifestError: The file is missing, is not JSON, or is invalid.
    """
    source = f"{package}/{filename}"
    try:
        raw = resources.files(package).joinpath(filename).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise ManifestError(f"Plugin manifest not found: {source}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Plugin manifest is not valid JSON ({source}): {exc}") from None
    if not isinstance(data, dict):
        raise ManifestError(f"Plugin manifest must be a JSON object ({source})")
    return parse_manifest(data, source=source)
