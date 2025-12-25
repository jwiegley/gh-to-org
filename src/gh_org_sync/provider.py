"""
Abstract provider protocol for issue sources.

This module defines the interface that both GitHub and Gitea clients implement,
allowing them to be used interchangeably by the sync orchestrator.
"""

from abc import ABC, abstractmethod
from enum import Enum

from .models import GitHubIssue


class ProviderType(str, Enum):
    """Supported issue provider types."""

    GITHUB = "github"
    GITEA = "gitea"


class IssueProvider(ABC):
    """
    Abstract base class for issue providers.

    Both GitHubClient and GiteaClient implement this interface,
    allowing the sync orchestrator to work with either provider.
    """

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close any resources held by the provider."""
        ...

    @abstractmethod
    async def check_connection(self) -> bool:
        """
        Check if the provider is accessible and authenticated.

        Returns:
            True if connection is successful

        Raises:
            Provider-specific exceptions on failure
        """
        ...

    @abstractmethod
    async def fetch_issues(
        self,
        repo: str,
        state: str = "all",
        limit: int | None = None,
        include_comments: bool = True,
    ) -> list[GitHubIssue]:
        """
        Fetch issues from the repository.

        Args:
            repo: Repository in owner/repo format
            state: Filter by state: 'open', 'closed', or 'all'
            limit: Maximum number of issues to fetch
            include_comments: Whether to include issue comments

        Returns:
            List of GitHubIssue objects (used as common format)
        """
        ...

    @abstractmethod
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
            include_comments: Whether to include comments

        Returns:
            GitHubIssue object
        """
        ...
