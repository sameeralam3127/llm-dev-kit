"""Interfaces core-api's services depend on. Adapters implement them."""

from core_api.ports.jobs import Blob, IngestionStore, Job, JobQueue
from core_api.ports.stores import (
    ApiKeyRecord,
    ApiKeyStore,
    AuditEvent,
    AuditSink,
    DocumentRecord,
    DocumentStore,
    Workspace,
    WorkspaceStore,
)

__all__ = [
    "ApiKeyRecord",
    "ApiKeyStore",
    "AuditEvent",
    "AuditSink",
    "Blob",
    "DocumentRecord",
    "DocumentStore",
    "IngestionStore",
    "Job",
    "JobQueue",
    "Workspace",
    "WorkspaceStore",
]
