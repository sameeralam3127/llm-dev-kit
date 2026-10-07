"""``StorageBackend``: keeps original uploaded files.

Today originals are discarded after chunking, so nothing can be re-indexed
(PLAN §1 item 10). A local volume backs it in core; S3 is a profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Metadata of a stored file.

    Attributes:
        key: Where it is stored, relative to the backend root.
        size: Bytes.
        content_type: MIME type given at upload.
        sha256: Hex digest of the content, for integrity and dedup.
    """

    key: str
    size: int
    content_type: str
    sha256: str


@runtime_checkable
class StorageBackend(Protocol):
    """A flat key/value store for file content.

    Keys are ``/``-separated relative paths. An implementation rejects keys
    that are absolute or escape its root (``..``).
    """

    @property
    def name(self) -> str:
        """Registry name, e.g. ``"fs"``, ``"s3"``."""
        ...

    async def put(self, key: str, data: bytes, *, content_type: str) -> StoredObject:
        """Store ``data`` at ``key``, replacing anything there."""
        ...

    async def get(self, key: str) -> bytes:
        """Return the content at ``key``.

        Raises:
            ldk_core.errors.ServiceError: ``not_found`` if absent.
        """
        ...

    async def delete(self, key: str) -> bool:
        """Remove ``key``; return whether it existed."""
        ...

    async def exists(self, key: str) -> bool:
        """Return whether ``key`` holds content."""
        ...
