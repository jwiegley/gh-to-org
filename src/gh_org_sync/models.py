"""
Pydantic models for GitHub issues and Org-mode structures.

This module defines the data models used throughout the application,
providing strong typing, validation, and serialization capabilities.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class IssueState(str, Enum):
    """GitHub issue state."""

    OPEN = "open"
    CLOSED = "closed"


class User(BaseModel):
    """GitHub user representation."""

    model_config = ConfigDict(frozen=True)

    login: str
    url: HttpUrl | None = None


class Label(BaseModel):
    """GitHub issue label."""

    model_config = ConfigDict(frozen=True)

    name: str
    color: str | None = None
    description: str | None = None


class Milestone(BaseModel):
    """GitHub milestone."""

    model_config = ConfigDict(frozen=True)

    title: str
    number: int
    state: str = "open"
    due_on: datetime | None = None


class Comment(BaseModel):
    """GitHub issue comment."""

    model_config = ConfigDict(frozen=True)

    id: int
    author: User
    body: str
    created_at: datetime
    updated_at: datetime | None = None
    url: HttpUrl | None = None


class GitHubIssue(BaseModel):
    """
    Complete GitHub issue with all metadata.

    This model represents the full data we receive from the GitHub CLI,
    including comments, labels, assignees, and timestamps.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    body: str | None = None
    state: IssueState
    state_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    author: User
    assignees: list[User] = Field(default_factory=list)
    labels: list[Label] = Field(default_factory=list)
    milestone: Milestone | None = None
    url: HttpUrl
    comments: list[Comment] = Field(default_factory=list)

    @property
    def label_names(self) -> list[str]:
        """Get list of label names."""
        return [label.name for label in self.labels]

    @property
    def assignee_logins(self) -> list[str]:
        """Get list of assignee login names."""
        return [a.login for a in self.assignees]


class OrgTodoState(str, Enum):
    """Org-mode TODO states."""

    TODO = "TODO"
    DONE = "DONE"


class OrgHeading(BaseModel):
    """
    Org-mode heading representation.

    This model captures the structure of an Org-mode heading including
    its properties drawer, content, tags, and child headings.
    """

    model_config = ConfigDict(frozen=False)  # Allow modification for merging

    level: int = Field(ge=1, le=10)
    title: str
    todo_state: OrgTodoState | None = None
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)
    content: str = ""
    children: list["OrgHeading"] = Field(default_factory=list)

    # Source tracking for merge operations
    source_line: int | None = None  # Line number in original file

    @property
    def github_number(self) -> int | None:
        """Get GitHub issue number from properties if present."""
        num_str = self.properties.get("GITHUB_NUMBER")
        if num_str:
            try:
                return int(num_str)
            except ValueError:
                return None
        return None

    @property
    def github_updated(self) -> datetime | None:
        """Get GitHub updated timestamp from properties if present."""
        updated_str = self.properties.get("GITHUB_UPDATED")
        if updated_str:
            try:
                return datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @property
    def is_github_synced(self) -> bool:
        """Check if this heading is synced from GitHub."""
        return "GITHUB_NUMBER" in self.properties

    @property
    def url(self) -> str | None:
        """Get URL from properties."""
        return self.properties.get("URL")

    def has_tag(self, tag: str) -> bool:
        """Check if heading has a specific tag."""
        return tag.upper() in [t.upper() for t in self.tags]


class MergeAction(str, Enum):
    """Type of merge action taken."""

    ADDED = "added"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    PRESERVED = "preserved"  # User content preserved


class MergeEntry(BaseModel):
    """Record of a single merge operation."""

    model_config = ConfigDict(frozen=True)

    issue_number: int
    title: str
    action: MergeAction
    details: str | None = None


class MergeResult(BaseModel):
    """Result of a merge operation."""

    model_config = ConfigDict(frozen=False)

    entries: list[MergeEntry] = Field(default_factory=list)
    total_github_issues: int = 0
    total_org_headings: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    preserved: int = 0  # User entries without GitHub link
    errors: list[str] = Field(default_factory=list)

    def add_entry(
        self,
        issue_number: int,
        title: str,
        action: MergeAction,
        details: str | None = None,
    ) -> None:
        """Add a merge entry and update counters."""
        self.entries.append(
            MergeEntry(
                issue_number=issue_number,
                title=title,
                action=action,
                details=details,
            )
        )
        if action == MergeAction.ADDED:
            self.added += 1
        elif action == MergeAction.UPDATED:
            self.updated += 1
        elif action == MergeAction.UNCHANGED:
            self.unchanged += 1
        elif action == MergeAction.PRESERVED:
            self.preserved += 1

    @property
    def has_changes(self) -> bool:
        """Check if any changes were made."""
        return self.added > 0 or self.updated > 0

    def summary(self) -> str:
        """Generate human-readable summary."""
        gh_count = self.total_github_issues
        org_count = self.total_org_headings
        lines = [
            f"Merge complete: {gh_count} GitHub issues, {org_count} Org headings",
            f"  Added: {self.added}",
            f"  Updated: {self.updated}",
            f"  Unchanged: {self.unchanged}",
            f"  Preserved (user entries): {self.preserved}",
        ]
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for error in self.errors[:5]:  # Show first 5 errors
                lines.append(f"    - {error}")
            if len(self.errors) > 5:
                lines.append(f"    ... and {len(self.errors) - 5} more")
        return "\n".join(lines)


class SyncConfig(BaseModel):
    """Configuration for sync operations."""

    model_config = ConfigDict(frozen=True)

    repo: str  # Format: owner/repo
    output_file: str
    state_filter: IssueState | str = "all"
    limit: int | None = None
    include_comments: bool = True
    dry_run: bool = False
    backup: bool = True

    @property
    def owner(self) -> str:
        """Get repository owner."""
        return self.repo.split("/")[0]

    @property
    def repo_name(self) -> str:
        """Get repository name."""
        parts = self.repo.split("/")
        return parts[1] if len(parts) > 1 else parts[0]
