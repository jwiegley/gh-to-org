"""
Exception hierarchy for gh-org-sync.

This module defines custom exceptions with clear messages and
actionable guidance for users.
"""


class GitHubOrgSyncError(Exception):
    """Base exception for all gh-org-sync errors."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}\n\nHint: {self.hint}"
        return self.message


# GitHub CLI Errors


class GitHubClientError(GitHubOrgSyncError):
    """Base class for GitHub CLI related errors."""


class GitHubCLINotFoundError(GitHubClientError):
    """The gh CLI tool is not installed or not in PATH."""

    def __init__(self) -> None:
        super().__init__(
            "GitHub CLI (gh) not found",
            "Install it from https://cli.github.com/ and ensure it's in your PATH",
        )


class GitHubAuthError(GitHubClientError):
    """GitHub authentication failed or not configured."""

    def __init__(self, details: str = "") -> None:
        message = "GitHub authentication failed"
        if details:
            message = f"{message}: {details}"
        super().__init__(
            message,
            "Run 'gh auth login' to authenticate with GitHub",
        )


class GitHubAPIError(GitHubClientError):
    """GitHub API returned an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        status_info = f" (HTTP {status_code})" if status_code else ""
        super().__init__(
            f"GitHub API error{status_info}: {message}",
            "Check that the repository exists and you have access to it",
        )


class GitHubNetworkError(GitHubClientError):
    """Network error communicating with GitHub."""

    def __init__(self, details: str = "") -> None:
        message = "Network error connecting to GitHub"
        if details:
            message = f"{message}: {details}"
        super().__init__(
            message,
            "Check your internet connection and try again",
        )


class GitHubRateLimitError(GitHubClientError):
    """GitHub API rate limit exceeded."""

    def __init__(self, reset_time: str | None = None) -> None:
        message = "GitHub API rate limit exceeded"
        hint = "Wait a few minutes and try again"
        if reset_time:
            hint = f"Rate limit resets at {reset_time}. Wait and try again."
        super().__init__(message, hint)


class GitHubTimeoutError(GitHubClientError):
    """GitHub CLI command timed out."""

    def __init__(self, timeout_seconds: int) -> None:
        super().__init__(
            f"GitHub CLI command timed out after {timeout_seconds} seconds",
            "Try reducing the number of issues with --limit or check your network",
        )


# Org File Errors


class OrgFileError(GitHubOrgSyncError):
    """Base class for Org file related errors."""


class OrgParseError(OrgFileError):
    """Failed to parse Org file."""

    def __init__(self, file_path: str, line: int | None = None, details: str = "") -> None:
        location = f" at line {line}" if line else ""
        message = f"Failed to parse Org file '{file_path}'{location}"
        if details:
            message = f"{message}: {details}"
        super().__init__(
            message,
            "Check that the file is valid Org-mode format",
        )


class OrgWriteError(OrgFileError):
    """Failed to write Org file."""

    def __init__(self, file_path: str, details: str = "") -> None:
        message = f"Failed to write Org file '{file_path}'"
        if details:
            message = f"{message}: {details}"
        super().__init__(
            message,
            "Check that you have write permissions and the directory exists",
        )


class OrgBackupError(OrgFileError):
    """Failed to create backup of Org file."""

    def __init__(self, file_path: str, details: str = "") -> None:
        message = f"Failed to create backup of '{file_path}'"
        if details:
            message = f"{message}: {details}"
        super().__init__(
            message,
            "Check disk space and permissions, or use --no-backup",
        )


# Merge Errors


class MergeError(GitHubOrgSyncError):
    """Base class for merge related errors."""


class MergeConflictError(MergeError):
    """Conflict detected during merge."""

    def __init__(self, issue_number: int, details: str = "") -> None:
        message = f"Merge conflict for issue #{issue_number}"
        if details:
            message = f"{message}: {details}"
        super().__init__(
            message,
            "Manually resolve the conflict in the Org file and re-run sync",
        )


# Configuration Errors


class ConfigError(GitHubOrgSyncError):
    """Configuration error."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)


class InvalidRepositoryError(ConfigError):
    """Invalid repository format."""

    def __init__(self, repo: str) -> None:
        super().__init__(
            f"Invalid repository format: '{repo}'",
            "Use format 'owner/repo', e.g., 'octocat/Hello-World'",
        )
