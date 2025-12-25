"""
Gitea API client for fetching issues.

This module handles all interactions with the Gitea REST API,
including fetching issues, comments, and handling authentication.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from .exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNetworkError,
    GitHubRateLimitError,
    GitHubTimeoutError,
)
from .models import Comment, GitHubIssue, IssueState, Label, Milestone, User
from .provider import IssueProvider, ProviderType

logger = logging.getLogger(__name__)


class GiteaClient(IssueProvider):
    """
    Client for interacting with Gitea via its REST API.

    This client provides async methods for fetching issues and comments,
    with proper error handling and timeout management.
    """

    DEFAULT_TIMEOUT = 60  # seconds
    DEFAULT_PAGE_SIZE = 50

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize the Gitea client.

        Args:
            base_url: Base URL of the Gitea instance (e.g., https://gitea.example.com)
            token: API token for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.GITEA

    @property
    def api_url(self) -> str:
        """Get the API base URL."""
        return f"{self.base_url}/api/v1"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Make an API request with error handling.

        Args:
            method: HTTP method
            path: API path (without base URL)
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Various GitHubClientError subclasses based on failure type
        """
        client = await self._get_client()

        try:
            response = await client.request(method, path, params=params)

            if response.status_code == 401:
                raise GitHubAuthError("Invalid or expired API token")

            if response.status_code == 403:
                if "rate limit" in response.text.lower():
                    raise GitHubRateLimitError
                raise GitHubAuthError(f"Access forbidden: {response.text}")

            if response.status_code == 404:
                raise GitHubAPIError(f"Not found: {path}", 404)

            if response.status_code >= 400:
                raise GitHubAPIError(response.text, response.status_code)

            return response.json()

        except httpx.TimeoutException as e:
            raise GitHubTimeoutError(self.timeout) from e

        except httpx.ConnectError as e:
            raise GitHubNetworkError(str(e)) from e

        except httpx.HTTPStatusError as e:
            raise GitHubAPIError(str(e), e.response.status_code) from e

    async def check_connection(self) -> bool:
        """
        Check if the Gitea instance is accessible and token is valid.

        Returns:
            True if connection is successful

        Raises:
            GitHubAuthError: If authentication fails
            GitHubNetworkError: If connection fails
        """
        try:
            # Try to get the current user to verify authentication
            await self._request("GET", "/user")
            return True
        except GitHubAPIError as e:
            if e.args and "404" in str(e.args[0]):
                # /user endpoint might not exist, try /version
                try:
                    await self._request("GET", "/version")
                    return True
                except Exception as version_err:
                    logger.debug(f"Fallback /version check failed: {version_err}")
            raise

    def _parse_user(self, data: dict[str, Any] | None) -> User:
        """Parse user data from Gitea API response."""
        if data is None:
            return User(login="unknown")
        return User(
            login=data.get("login") or data.get("username", "unknown"),
            url=data.get("html_url") or data.get("avatar_url"),
        )

    def _parse_label(self, data: dict[str, Any]) -> Label:
        """Parse label data from Gitea API response."""
        return Label(
            name=data.get("name", ""),
            color=data.get("color"),
            description=data.get("description"),
        )

    def _parse_milestone(self, data: dict[str, Any] | None) -> Milestone | None:
        """Parse milestone data from Gitea API response."""
        if not data:
            return None
        return Milestone(
            title=data.get("title", ""),
            number=data.get("id", 0),
            state=data.get("state", "open"),
            due_on=self._parse_datetime(data.get("due_on")),
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse ISO datetime string from Gitea API."""
        if not value:
            return None
        try:
            # Gitea uses ISO 8601 format
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse datetime: {value}")
            return None

    def _parse_comment(self, data: dict[str, Any]) -> Comment:
        """Parse comment data from Gitea API response."""
        return Comment(
            id=data.get("id", 0),
            author=self._parse_user(data.get("user")),
            body=data.get("body", ""),
            created_at=self._parse_datetime(data.get("created_at")) or datetime.now(UTC),
            updated_at=self._parse_datetime(data.get("updated_at")),
            url=data.get("html_url"),
        )

    def _parse_issue(
        self,
        data: dict[str, Any],
        comments: list[Comment] | None = None,
    ) -> GitHubIssue:
        """Parse issue JSON from Gitea API into GitHubIssue model."""
        # Parse nested objects
        author = self._parse_user(data.get("user"))
        assignees = [self._parse_user(a) for a in data.get("assignees") or []]
        labels = [self._parse_label(lbl) for lbl in data.get("labels") or []]
        milestone = self._parse_milestone(data.get("milestone"))

        # Parse state - Gitea uses "open" and "closed"
        state_str = data.get("state", "open").lower()
        state = IssueState.CLOSED if state_str == "closed" else IssueState.OPEN

        # Use provided comments or empty list
        issue_comments = comments if comments is not None else []

        return GitHubIssue(
            number=data.get("number", 0),
            title=data.get("title", "Untitled"),
            body=data.get("body"),
            state=state,
            state_reason=None,  # Gitea doesn't have state_reason
            created_at=self._parse_datetime(data.get("created_at")) or datetime.now(UTC),
            updated_at=self._parse_datetime(data.get("updated_at")) or datetime.now(UTC),
            closed_at=self._parse_datetime(data.get("closed_at")),
            author=author,
            assignees=assignees,
            labels=labels,
            milestone=milestone,
            url=data.get("html_url", ""),
            comments=sorted(issue_comments, key=lambda c: c.created_at),
        )

    async def _fetch_comments(self, repo: str, issue_number: int) -> list[Comment]:
        """
        Fetch comments for an issue.

        Args:
            repo: Repository in owner/repo format
            issue_number: Issue number

        Returns:
            List of Comment objects
        """
        path = f"/repos/{repo}/issues/{issue_number}/comments"

        try:
            comments_data = await self._request("GET", path)

            if not isinstance(comments_data, list):
                return []

            return [self._parse_comment(c) for c in comments_data]

        except GitHubAPIError as e:
            logger.warning(f"Failed to fetch comments for issue #{issue_number}: {e}")
            return []

    async def fetch_issues(
        self,
        repo: str,
        state: str = "all",
        limit: int | None = None,
        include_comments: bool = True,
    ) -> list[GitHubIssue]:
        """
        Fetch issues from a Gitea repository.

        Args:
            repo: Repository in owner/repo format
            state: Filter by state: 'open', 'closed', or 'all'
            limit: Maximum number of issues to fetch (None for all)
            include_comments: Whether to fetch comments for each issue

        Returns:
            List of GitHubIssue objects sorted by number
        """
        logger.info(f"Fetching issues from Gitea: {repo} (state={state}, limit={limit})")

        all_issues: list[GitHubIssue] = []
        page = 1
        page_size = min(limit or self.DEFAULT_PAGE_SIZE, self.DEFAULT_PAGE_SIZE)

        while True:
            params: dict[str, Any] = {
                "state": state,
                "page": page,
                "limit": page_size,
                "type": "issues",  # Exclude pull requests
            }

            path = f"/repos/{repo}/issues"
            issues_data = await self._request("GET", path, params=params)

            if not isinstance(issues_data, list):
                break

            if not issues_data:
                break  # No more issues

            for issue_data in issues_data:
                # Fetch comments if requested
                comments: list[Comment] = []
                if include_comments:
                    issue_number = issue_data.get("number", 0)
                    if issue_number > 0:
                        comments = await self._fetch_comments(repo, issue_number)

                issue = self._parse_issue(issue_data, comments)
                all_issues.append(issue)

                # Check if we've reached the limit
                if limit is not None and len(all_issues) >= limit:
                    break

            # Check if we've reached the limit or got fewer than requested
            if limit is not None and len(all_issues) >= limit:
                break

            if len(issues_data) < page_size:
                break  # Last page

            page += 1

        # Sort by issue number
        all_issues.sort(key=lambda i: i.number)

        logger.info(f"Fetched {len(all_issues)} issues from Gitea")
        return all_issues[:limit] if limit else all_issues

    async def fetch_issue(
        self,
        repo: str,
        number: int,
        include_comments: bool = True,
    ) -> GitHubIssue:
        """
        Fetch a single issue by number.

        Args:
            repo: Repository in owner/repo format
            number: Issue number
            include_comments: Whether to fetch comments

        Returns:
            GitHubIssue object
        """
        path = f"/repos/{repo}/issues/{number}"
        issue_data = await self._request("GET", path)

        comments: list[Comment] = []
        if include_comments:
            comments = await self._fetch_comments(repo, number)

        return self._parse_issue(issue_data, comments)
