"""``RateLimiter``: may this caller do this now?

Replaces the in-process limiter in ``web/src/server/rate-limit.ts`` with one
shared across replicas (Redis token bucket in Phase 6). Buckets keep chat,
ingest and auth limits separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """The outcome of one :meth:`RateLimiter.hit`.

    Attributes:
        allowed: Whether the request may proceed.
        limit: Capacity of the bucket.
        remaining: Tokens left after this hit (0 when refused).
        retry_after: Seconds until a retry can succeed, when refused; becomes
            the ``Retry-After`` header.
    """

    allowed: bool
    limit: int
    remaining: int
    retry_after: float | None = None


@runtime_checkable
class RateLimiter(Protocol):
    """Token-bucket style limiter keyed by bucket and caller."""

    @property
    def name(self) -> str:
        """Registry name, e.g. ``"redis"``, ``"memory"``."""
        ...

    async def hit(self, bucket: str, key: str, *, cost: int = 1) -> RateLimitDecision:
        """Spend ``cost`` tokens from ``bucket`` for ``key`` if available.

        Args:
            bucket: The policy to apply, e.g. ``"chat"``, ``"ingest"``, ``"auth"``.
            key: Who is being limited, e.g. ``"user:<id>"`` or ``"ip:<addr>"``.
            cost: Tokens this request consumes.

        A refused hit consumes nothing. If the backing store is down the
        limiter fails open and logs it, rather than taking the product down.
        """
        ...
