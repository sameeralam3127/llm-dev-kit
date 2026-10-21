"""Upload and list documents. Ingestion itself happens in the ingest-worker."""

from __future__ import annotations

import hashlib

from core_api.domain.access import Access
from core_api.ports.stores import AuditEvent, AuditSink, DocumentRecord, DocumentStore
from ldk_core.auth import forbidden
from ldk_core.errors import bad_request

#: The gateway already refuses bodies over 64 MB; this keeps core-api honest
#: when it is reached some other way.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
PDF_MAGIC = b"%PDF-"


class DocumentService:
    """Use cases for ``/api/v1/documents``."""

    def __init__(self, *, documents: DocumentStore, audit: AuditSink) -> None:
        self._documents = documents
        self._audit = audit

    async def upload(
        self, access: Access, *, filename: str, data: bytes, request_id: str | None
    ) -> tuple[DocumentRecord, bool]:
        """Store an upload and queue it for ingestion.

        Returns the document and whether it is new. The same bytes uploaded
        again to the same workspace return the existing document and queue
        nothing: ``content_hash`` makes ingestion idempotent.
        """
        if not access.allows("ingest"):
            raise forbidden("ingest")
        if not data:
            raise bad_request("The file is empty")
        if len(data) > MAX_UPLOAD_BYTES:
            raise bad_request("The file is larger than 64 MB")
        # Trust the bytes, not the client's Content-Type.
        if not data.startswith(PDF_MAGIC):
            raise bad_request("Only PDF files can be uploaded for now")

        document, created = await self._documents.create_upload(
            workspace_id=access.workspace_id,
            user_id=access.user_id,
            filename=filename,
            media_type="application/pdf",
            data=data,
            content_hash=hashlib.sha256(data).digest(),
        )
        await self._audit.record(
            AuditEvent(
                actor=access.user_id,
                workspace_id=access.workspace_id,
                action="document.upload" if created else "document.upload_duplicate",
                resource=f"document:{document.id}",
                request_id=request_id,
                detail={"bytes": len(data), "via": access.via},
            )
        )
        return document, created

    async def list(self, access: Access) -> list[DocumentRecord]:
        """The workspace's documents."""
        if not access.allows("chat"):
            raise forbidden("chat")
        return await self._documents.documents_of(access.workspace_id)
