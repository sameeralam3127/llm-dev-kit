"""llm-dev-kit plugin: cloud chat models through LiteLLM.

Provides ``llm.openai``, ``llm.gemini`` and ``llm.anthropic``.
"""

from collections.abc import Callable, Mapping
from typing import Any

from ldk_core.plugins import Plugin, load_manifest
from ldk_plugin_litellm.provider import DEFAULT_CLOUD_MODELS, LiteLLMProvider


def _factory(name: str) -> Callable[[Mapping[str, Any]], LiteLLMProvider]:
    def build(config: Mapping[str, Any]) -> LiteLLMProvider:
        return LiteLLMProvider(
            name,
            config.get("api_key"),
            base_url=config.get("base_url"),
            timeout_seconds=config.get("timeout_seconds", 120),
        )

    return build


def _plugin(name: str) -> Plugin:
    return Plugin(load_manifest(__name__, f"manifests/llm.{name}.json"), _factory(name))


openai_plugin = _plugin("openai")
gemini_plugin = _plugin("gemini")
anthropic_plugin = _plugin("anthropic")

__all__ = [
    "DEFAULT_CLOUD_MODELS",
    "LiteLLMProvider",
    "anthropic_plugin",
    "gemini_plugin",
    "openai_plugin",
]
