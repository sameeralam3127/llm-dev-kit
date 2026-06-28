from app.config import Settings, get_settings
from app.interfaces import GitHubClient


class GitHubRetriever:
    def __init__(self, *, github: GitHubClient, settings: Settings | None = None) -> None:
        self.github = github
        self.settings = settings or get_settings()

    async def retrieve(self, question: str) -> list[str]:
        owner = self.settings.github_default_owner
        repo = self.settings.github_default_repo
        branch = self.settings.github_default_branch
        if not owner or not repo:
            return []

        events = await self.github.search_markdown(owner, repo, question, branch)
        docs: list[str] = []
        for event in events:
            docs.append(
                await self.github.download_markdown(owner, event.repo, event.path, branch)
            )
        return docs
