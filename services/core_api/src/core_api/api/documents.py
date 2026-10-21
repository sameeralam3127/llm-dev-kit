"""/api/v1/documents: upload a PDF, list a workspace's documents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from pydantic import BaseModel

from core_api.api.deps import CurrentWorkspaceDep, RequestIdDep, authenticated
from core_api.ports.stores import DocumentRecord
from core_api.services.documents import MAX_UPLOAD_BYTES, DocumentService

router = APIRouter(
    prefix="/api/v1/documents", tags=["documents"], dependencies=[Depends(authenticated)]
)


class DocumentOut(BaseModel):
    """A document and where its ingestion stands."""

    id: UUID
    workspace_id: UUID
    title: str | None
    status: str
    chunk_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, d: DocumentRecord) -> DocumentOut:
        """Serialise a document."""
        return cls(
            id=d.id,
            workspace_id=d.workspace_id,
            title=d.title,
            status=d.status,
            chunk_count=d.chunk_count,
            last_error=d.last_error if d.status == "failed" else None,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )


def _service(request: Request) -> DocumentService:
    service: DocumentService = request.app.state.documents
    return service


@router.post("", status_code=202)
async def upload(
    access: CurrentWorkspaceDep,
    request: Request,
    response: Response,
    rid: RequestIdDep,
    file: UploadFile = File(...),
) -> dict[str, object]:
    """Upload a PDF. 202: queued for ingestion; 200: already in this workspace."""
    # Read one byte past the limit, so an oversized file is refused without
    # holding more than the limit in memory.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    document, created = await _service(request).upload(
        access, filename=file.filename or "document.pdf", data=data, request_id=rid
    )
    if not created:
        response.status_code = 200
    return {"data": DocumentOut.of(document), "duplicate": not created}


@router.get("")
async def list_documents(
    access: CurrentWorkspaceDep, request: Request
) -> dict[str, list[DocumentOut]]:
    """The workspace's documents, newest first."""
    return {"data": [DocumentOut.of(d) for d in await _service(request).list(access)]}
