"""Which model calls send data off the network: the sovereignty decision.

A model id names its provider with a prefix (``openai/gpt-4o``); anything
without a cloud prefix is a model on the local Ollama. Two kinds of call leave
the network:

* any provider other than the local Ollama;
* an Ollama *cloud* model (``gpt-oss:120b-cloud``, ``glm-4.6:cloud``), which
  Ollama forwards to ollama.com instead of running it.

Sovereign mode refuses both before anything is sent.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

LOCAL_PROVIDER = "ollama"

CLOUD_PROVIDERS = frozenset({"openai", "gemini", "anthropic"})
"""Prefixes that always mean a cloud provider, loaded or not.

Sovereign mode loads none of them, so without this list ``openai/gpt-4o``
would be looked up as a local model instead of being refused as egress.
"""


@dataclass(frozen=True, slots=True)
class Route:
    """Where a model id goes.

    Attributes:
        provider: Registry name of the provider, e.g. ``"ollama"``.
        model: The provider's own id, with the routing prefix removed.
        egress: Whether the call would send data off the network.
    """

    provider: str
    model: str
    egress: bool


def is_ollama_cloud(model: str) -> bool:
    """Whether an Ollama model runs on ollama.com rather than locally.

    Ollama names them with a ``cloud`` tag or a ``-cloud`` suffix:
    ``gpt-oss:120b-cloud``, ``glm-4.6:cloud``, ``kimi-k2-cloud``.
    """
    base, _, tag = model.strip().lower().partition(":")
    return tag == "cloud" or tag.endswith("-cloud") or base.endswith("-cloud")


def route(model: str, cloud: Collection[str] = ()) -> Route:
    """Route a model id.

    Args:
        model: The id a caller asked for.
        cloud: Cloud providers this gateway has loaded, in addition to
            :data:`CLOUD_PROVIDERS`.
    """
    prefix, sep, rest = model.partition("/")
    if sep and rest and (prefix in CLOUD_PROVIDERS or prefix in cloud):
        return Route(prefix, rest, egress=True)
    return Route(LOCAL_PROVIDER, model, egress=is_ollama_cloud(model))
