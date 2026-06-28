import asyncio
from typing import Any
from urllib.parse import quote

from app.config import Settings, get_settings
from app.models.events import DocsChangedEvent, DocumentEventType


class GitHubApiError(RuntimeError):
    pass


class HttpGitHubClient:
    def __init__(
        self,
        *,
        token: str | None,
        timeout: float = 20.0,
        retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self.token = token
        self.timeout = timeout
        self.retries = retries
        self.backoff_seconds = backoff_seconds

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "HttpGitHubClient":
        settings = settings or get_settings()
        return cls(token=settings.github_token)

    def _headers(self, accept: str = "application/vnd.github+json") -> dict[str, str]:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "llm-dev-kit-doc-sync",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request(self, url: str, *, accept: str | None = None) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("Install httpx to use the GitHub client") from exc

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.retries):
                response = await client.get(
                    url, headers=self._headers(accept or "application/vnd.github+json")
                )
                if response.status_code == 403 and response.headers.get(
                    "x-ratelimit-remaining"
                ) == "0":
                    reset_at = int(response.headers.get("x-ratelimit-reset", "0"))
                    raise GitHubApiError(f"GitHub rate limit exceeded until {reset_at}")
                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = GitHubApiError(
                        f"GitHub transient error {response.status_code}"
                    )
                    await asyncio.sleep(self.backoff_seconds * (2**attempt))
                    continue
                if response.is_error:
                    raise GitHubApiError(
                        f"GitHub error {response.status_code}: {response.text[:200]}"
                    )
                if accept == "application/vnd.github.raw":
                    return response.text
                return response.json()
        raise GitHubApiError(str(last_error or "GitHub request failed"))

    async def download_markdown(
        self, owner: str, repo: str, path: str, branch: str
    ) -> str:
        encoded_path = quote(path)
        url = (
            f"https://api.github.com/repos/{owner}/{repo}/contents/"
            f"{encoded_path}?ref={quote(branch)}"
        )
        return str(await self._request(url, accept="application/vnd.github.raw"))

    async def latest_commit_sha(
        self, owner: str, repo: str, path: str, branch: str
    ) -> str:
        query = quote(path)
        url = (
            f"https://api.github.com/repos/{owner}/{repo}/commits"
            f"?path={query}&sha={quote(branch)}&per_page=1"
        )
        commits = await self._request(url)
        if not commits:
            return ""
        return str(commits[0]["sha"])

    async def repository_metadata(self, owner: str, repo: str) -> dict[str, Any]:
        return dict(
            await self._request(f"https://api.github.com/repos/{owner}/{repo}")
        )

    async def search_markdown(
        self, owner: str, repo: str, query: str, branch: str
    ) -> list[DocsChangedEvent]:
        items: list[dict[str, Any]] = []
        for extension in ("md", "mdx"):
            search_query = quote(f"repo:{owner}/{repo} {query} extension:{extension}")
            url = f"https://api.github.com/search/code?q={search_query}&per_page=10"
            result = await self._request(url)
            items.extend(result.get("items", []))

        events: list[DocsChangedEvent] = []
        seen: set[str] = set()
        for item in items:
            path = item.get("path", "")
            if not path.endswith((".md", ".mdx")) or path in seen:
                continue
            seen.add(path)
            events.append(
                DocsChangedEvent(
                    owner=owner,
                    repo=repo,
                    branch=branch,
                    path=path,
                    commit=await self.latest_commit_sha(owner, repo, path, branch),
                    event=DocumentEventType.MODIFIED,
                    url=item.get("html_url"),
                )
            )
        return events
