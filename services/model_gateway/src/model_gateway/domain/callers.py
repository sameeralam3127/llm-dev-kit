"""Who may call the gateway: internal services, each with its own token.

Users never call the gateway. core-api authenticates them and says on whose
behalf it calls; the gateway trusts that only because the service token
proves the request came from core-api. Each service gets only what it needs,
so a compromised ingest-worker can embed text but cannot chat with a model.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

Permission = Literal["models", "chat", "embed"]


@dataclass(frozen=True, slots=True)
class Service:
    """A calling service and what it may do."""

    name: str
    permissions: frozenset[Permission]
    token: bytes = field(repr=False)


def core_api(token: str) -> Service:
    """core-api: lists models, chats on behalf of users, embeds questions."""
    return Service("core-api", frozenset({"models", "chat", "embed"}), token.encode())


def ingest_worker(token: str) -> Service:
    """The ingest-worker: embeds document chunks, nothing else."""
    return Service("ingest-worker", frozenset({"embed"}), token.encode())


def identify(token: str | None, services: Iterable[Service]) -> Service | None:
    """The service whose token this is, or ``None``.

    Compares against every service's token in constant time, without stopping
    at a match, so response timing says nothing about which token was close.
    """
    if not token:
        return None
    given = token.encode()
    found: Service | None = None
    for service in services:
        if hmac.compare_digest(given, service.token):
            found = service
    return found
