from app.config import Settings, get_settings
from app.interfaces import EventBus, GitHubClient
from app.models.events import DocsChangedEvent, DocumentEventType
from app.retrievers.github import GitHubRetriever
from app.retrievers.vector import VectorRetriever


class GitHubHybridRetriever:
    def __init__(
        self,
        *,
        vector_retriever: VectorRetriever,
        github_retriever: GitHubRetriever,
        github: GitHubClient,
        event_bus: EventBus,
        settings: Settings | None = None,
    ) -> None:
        self.vector_retriever = vector_retriever
        self.github_retriever = github_retriever
        self.github = github
        self.event_bus = event_bus
        self.settings = settings or get_settings()

    async def retrieve(self, question: str) -> list[str]:
        vector_results = await self.vector_retriever.retrieve_with_metadata(question)
        fresh_docs: list[str] = []

        for result in vector_results:
            payload = result.get("payload", {})
            owner = payload.get("owner") or self.settings.github_default_owner
            repo = payload.get("repo")
            path = payload.get("path")
            branch = payload.get("branch") or self.settings.github_default_branch
            commit = payload.get("commit")
            if not owner or not repo or not path:
                continue

            latest = await self.github.latest_commit_sha(owner, repo, path, branch)
            if latest and latest != commit:
                markdown = await self.github.download_markdown(owner, repo, path, branch)
                fresh_docs.append(markdown)
                await self.event_bus.publish(
                    self.settings.kafka_topic_docs_changed,
                    DocsChangedEvent(
                        owner=owner,
                        repo=repo,
                        branch=branch,
                        path=path,
                        commit=latest,
                        event=DocumentEventType.MODIFIED,
                        url=payload.get("url") or None,
                    ),
                    key=path,
                )
            else:
                fresh_docs.append(str(payload.get("text", "")))

        if fresh_docs:
            return fresh_docs

        docs = await self.github_retriever.retrieve(question)
        await self._publish_background_updates(question)
        return docs

    async def _publish_background_updates(self, question: str) -> None:
        owner = self.settings.github_default_owner
        repo = self.settings.github_default_repo
        branch = self.settings.github_default_branch
        if not owner or not repo:
            return

        events = await self.github.search_markdown(owner, repo, question, branch)
        for event in events:
            await self.event_bus.publish(
                self.settings.kafka_topic_docs_changed, event, key=event.path
            )
