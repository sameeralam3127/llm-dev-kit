import asyncio
from typing import Any
from urllib.parse import quote

from devkit_common.config import Settings, get_settings


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
        self._client = None

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "HttpGitHubClient":
        settings = settings or get_settings()
        return cls(token=settings.github_token)

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
            except ImportError as exc:
                raise RuntimeError("Install httpx to use the GitHub client") from exc
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

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
        import httpx

        client = self._get_client()
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = await client.get(
                    url, headers=self._headers(accept or "application/vnd.github+json")
                )
            except httpx.HTTPError as exc:
                last_error = exc
                await asyncio.sleep(self.backoff_seconds * (2**attempt))
                continue
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

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
