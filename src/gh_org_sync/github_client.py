"""
GitHub CLI client for fetching issues.

This module handles all interactions with the GitHub CLI (gh),
including fetching issues, comments, and handling errors gracefully.
"""

import asyncio
import json
import logging
import shutil
from datetime import UTC, datetime
from typing import Any

from .exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubCLINotFoundError,
    GitHubNetworkError,
    GitHubRateLimitError,
    GitHubTimeoutError,
)
from .models import Comment, GitHubIssue, IssueState, Label, Milestone, User
from .provider import IssueProvider, ProviderType

logger = logging.getLogger(__name__)


class GitHubClient(IssueProvider):
    """
    Client for interacting with GitHub via the gh CLI.

    This client provides async methods for fetching issues and comments,
    with proper error handling, retry logic, and timeout management.
    """

    DEFAULT_TIMEOUT = 60  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """
        Initialize the GitHub client.

        Args:
            timeout: Command timeout in seconds
        """
        self.timeout = timeout

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.GITHUB

    async def close(self) -> None:
        """Close the client (no-op for CLI-based client)."""

    async def check_connection(self) -> bool:
        """
        Check if the GitHub CLI is available and authenticated.

        Returns:
            True if connection is successful

        Raises:
            GitHubCLINotFoundError: If gh CLI is not found
            GitHubAuthError: If not authenticated
        """
        await self.check_cli_available()
        return await self.check_auth()

    async def check_cli_available(self) -> bool:
        """
        Check if gh CLI is installed and in PATH.

        Returns:
            True if gh is available

        Raises:
            GitHubCLINotFoundError: If gh is not found
        """
        if shutil.which("gh") is None:
            raise GitHubCLINotFoundError
        return True

    async def check_auth(self) -> bool:
        """
        Check if gh is authenticated.

        Returns:
            True if authenticated

        Raises:
            GitHubAuthError: If not authenticated
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "gh",
                "auth",
                "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                raise GitHubAuthError(error_msg)

            return True
        except TimeoutError:
            raise GitHubAuthError("Auth check timed out") from None
        except FileNotFoundError:
            raise GitHubCLINotFoundError from None

    async def _run_gh_command(
        self,
        args: list[str],
        retry_count: int = 0,
    ) -> str:
        """
        Execute a gh CLI command with error handling and retries.

        Args:
            args: Command arguments (without 'gh' prefix)
            retry_count: Current retry attempt

        Returns:
            Command stdout as string

        Raises:
            Various GitHubClientError subclasses based on failure type
        """
        cmd = ["gh", *args]
        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )

            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""

            if proc.returncode != 0:
                return self._handle_error(stderr_str, retry_count, args)

            return stdout_str

        except TimeoutError:
            if retry_count < self.MAX_RETRIES:
                msg = f"Command timed out, retrying ({retry_count + 1}/{self.MAX_RETRIES})"
                logger.warning(msg)
                await asyncio.sleep(self.RETRY_DELAY * (retry_count + 1))
                return await self._run_gh_command(args, retry_count + 1)
            raise GitHubTimeoutError(self.timeout) from None

        except FileNotFoundError:
            raise GitHubCLINotFoundError from None

    def _handle_error(
        self,
        stderr: str,
        retry_count: int,
        _args: list[str],
    ) -> str:
        """Handle gh CLI errors and determine if retry is appropriate."""
        stderr_lower = stderr.lower()

        # Check for specific error types
        if "not logged in" in stderr_lower or "authentication" in stderr_lower:
            raise GitHubAuthError(stderr.strip())

        if "rate limit" in stderr_lower:
            raise GitHubRateLimitError

        if "could not resolve" in stderr_lower or "network" in stderr_lower:
            if retry_count < self.MAX_RETRIES:
                logger.warning(f"Network error, will retry: {stderr.strip()}")
                # Note: This will be handled by the caller's retry logic
            raise GitHubNetworkError(stderr.strip())

        if "not found" in stderr_lower or "404" in stderr_lower:
            raise GitHubAPIError(stderr.strip(), 404)

        if "403" in stderr_lower:
            raise GitHubAPIError(stderr.strip(), 403)

        # Generic API error
        raise GitHubAPIError(stderr.strip())

    def _parse_user(self, data: dict[str, Any] | str | None) -> User:
        """Parse user data from various formats."""
        if data is None:
            return User(login="unknown")
        if isinstance(data, str):
            return User(login=data)
        return User(
            login=data.get("login", "unknown"),
            url=data.get("url"),
        )

    def _parse_label(self, data: dict[str, Any] | str) -> Label:
        """Parse label data."""
        if isinstance(data, str):
            return Label(name=data)
        return Label(
            name=data.get("name", ""),
            color=data.get("color"),
            description=data.get("description"),
        )

    def _parse_milestone(self, data: dict[str, Any] | None) -> Milestone | None:
        """Parse milestone data."""
        if not data:
            return None
        return Milestone(
            title=data.get("title", ""),
            number=data.get("number", 0),
            state=data.get("state", "open"),
            due_on=self._parse_datetime(data.get("dueOn")),
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        if not value:
            return None
        try:
            # Handle both Z suffix and +00:00 format
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse datetime: {value}")
            return None

    def _parse_comment(self, data: dict[str, Any]) -> Comment:
        """Parse comment data."""
        return Comment(
            id=data.get("id", 0),
            author=self._parse_user(data.get("author")),
            body=data.get("body", ""),
            created_at=self._parse_datetime(data.get("createdAt")) or datetime.now(UTC),
            updated_at=self._parse_datetime(data.get("updatedAt")),
            url=data.get("url"),
        )

    def _parse_issue(self, data: dict[str, Any]) -> GitHubIssue:
        """Parse issue JSON into GitHubIssue model."""
        # Parse nested objects
        author = self._parse_user(data.get("author"))
        assignees = [self._parse_user(a) for a in data.get("assignees", [])]
        labels = [self._parse_label(lbl) for lbl in data.get("labels", [])]
        milestone = self._parse_milestone(data.get("milestone"))

        # Parse comments
        comments_data = data.get("comments", [])
        if isinstance(comments_data, list):
            comments = [self._parse_comment(c) for c in comments_data]
        else:
            comments = []

        # Parse state
        state_str = data.get("state", "open").lower()
        state = IssueState.CLOSED if state_str == "closed" else IssueState.OPEN

        return GitHubIssue(
            number=data.get("number", 0),
            title=data.get("title", "Untitled"),
            body=data.get("body"),
            state=state,
            state_reason=data.get("stateReason"),
            created_at=self._parse_datetime(data.get("createdAt")) or datetime.now(UTC),
            updated_at=self._parse_datetime(data.get("updatedAt")) or datetime.now(UTC),
            closed_at=self._parse_datetime(data.get("closedAt")),
            author=author,
            assignees=assignees,
            labels=labels,
            milestone=milestone,
            url=data.get("url", ""),
            comments=sorted(comments, key=lambda c: c.created_at),
        )

    async def fetch_issues(
        self,
        repo: str,
        state: str = "all",
        limit: int | None = None,
        include_comments: bool = True,
    ) -> list[GitHubIssue]:
        """
        Fetch issues from a GitHub repository.

        Args:
            repo: Repository in owner/repo format
            state: Filter by state: 'open', 'closed', or 'all'
            limit: Maximum number of issues to fetch (None for all)
            include_comments: Whether to fetch comments for each issue

        Returns:
            List of GitHubIssue objects sorted by number
        """
        await self.check_cli_available()
        await self.check_auth()

        # Build the gh issue list command
        # Use JSON output with specific fields
        fields = [
            "number",
            "title",
            "body",
            "state",
            "stateReason",
            "createdAt",
            "updatedAt",
            "closedAt",
            "author",
            "assignees",
            "labels",
            "milestone",
            "url",
        ]

        if include_comments:
            fields.append("comments")

        args = [
            "issue",
            "list",
            "-R",
            repo,
            "--state",
            state,
            "--json",
            ",".join(fields),
        ]

        if limit is not None:
            args.extend(["--limit", str(limit)])
        else:
            # gh defaults to 30; use a high number for "all"
            args.extend(["--limit", "1000"])

        logger.info(f"Fetching issues from {repo} (state={state}, limit={limit})")

        output = await self._run_gh_command(args)

        if not output.strip():
            logger.info("No issues found")
            return []

        try:
            issues_data = json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise GitHubAPIError(f"Invalid JSON response: {e}") from e

        if not isinstance(issues_data, list):
            raise GitHubAPIError("Expected list of issues in response")

        issues = [self._parse_issue(data) for data in issues_data]

        # Sort by issue number
        issues.sort(key=lambda i: i.number)

        logger.info(f"Fetched {len(issues)} issues")
        return issues

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
        await self.check_cli_available()
        await self.check_auth()

        fields = [
            "number",
            "title",
            "body",
            "state",
            "stateReason",
            "createdAt",
            "updatedAt",
            "closedAt",
            "author",
            "assignees",
            "labels",
            "milestone",
            "url",
        ]

        if include_comments:
            fields.append("comments")

        args = [
            "issue",
            "view",
            "-R",
            repo,
            str(number),
            "--json",
            ",".join(fields),
        ]

        output = await self._run_gh_command(args)

        try:
            issue_data = json.loads(output)
        except json.JSONDecodeError as e:
            raise GitHubAPIError(f"Invalid JSON response: {e}") from e

        return self._parse_issue(issue_data)
