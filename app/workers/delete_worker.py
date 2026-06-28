from app.interfaces import VectorStore
from app.models.events import DocsChangedEvent


async def process_delete_event(
    event: DocsChangedEvent, *, vector_store: VectorStore
) -> None:
    await vector_store.delete_by_repo_path(repo=event.repo, path=event.path)
