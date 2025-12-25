"""Tests for Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from gh_org_sync.models import (
    GitHubIssue,
    IssueState,
    Label,
    MergeAction,
    MergeResult,
    OrgHeading,
    OrgTodoState,
    User,
)


class TestUser:
    """Tests for User model."""

    def test_create_user(self) -> None:
        user = User(login="testuser")
        assert user.login == "testuser"
        assert user.url is None

    def test_create_user_with_url(self) -> None:
        user = User(login="testuser", url="https://github.com/testuser")
        assert user.login == "testuser"
        assert "github.com/testuser" in str(user.url)


class TestLabel:
    """Tests for Label model."""

    def test_create_label(self) -> None:
        label = Label(name="bug", color="d73a4a")
        assert label.name == "bug"
        assert label.color == "d73a4a"


class TestGitHubIssue:
    """Tests for GitHubIssue model."""

    def test_create_issue(self, sample_issue: GitHubIssue) -> None:
        assert sample_issue.number == 123
        assert sample_issue.title == "Test Issue Title"
        assert sample_issue.state == IssueState.OPEN

    def test_label_names(self, sample_issue: GitHubIssue) -> None:
        assert sample_issue.label_names == ["bug", "enhancement"]

    def test_assignee_logins(self, sample_issue: GitHubIssue) -> None:
        assert sample_issue.assignee_logins == ["testuser"]


class TestOrgHeading:
    """Tests for OrgHeading model."""

    def test_create_heading(self) -> None:
        heading = OrgHeading(level=1, title="Test")
        assert heading.level == 1
        assert heading.title == "Test"
        assert heading.todo_state is None
        assert heading.tags == []
        assert heading.properties == {}

    def test_github_number_property(self) -> None:
        heading = OrgHeading(
            level=1,
            title="Test",
            properties={"GITHUB_NUMBER": "123"},
        )
        assert heading.github_number == 123

    def test_github_number_none_when_missing(self) -> None:
        heading = OrgHeading(level=1, title="Test")
        assert heading.github_number is None

    def test_is_github_synced(self) -> None:
        heading = OrgHeading(
            level=1,
            title="Test",
            properties={"GITHUB_NUMBER": "123"},
        )
        assert heading.is_github_synced is True

        heading2 = OrgHeading(level=1, title="Test")
        assert heading2.is_github_synced is False

    def test_has_tag(self) -> None:
        heading = OrgHeading(level=1, title="Test", tags=["LINK", "bug"])
        assert heading.has_tag("LINK") is True
        assert heading.has_tag("link") is True  # Case insensitive
        assert heading.has_tag("feature") is False


class TestMergeResult:
    """Tests for MergeResult model."""

    def test_add_entry(self) -> None:
        result = MergeResult()

        result.add_entry(1, "Issue 1", MergeAction.ADDED)
        assert result.added == 1

        result.add_entry(2, "Issue 2", MergeAction.UPDATED)
        assert result.updated == 1

        result.add_entry(3, "Issue 3", MergeAction.UNCHANGED)
        assert result.unchanged == 1

    def test_has_changes(self) -> None:
        result = MergeResult()
        assert result.has_changes is False

        result.add_entry(1, "Issue 1", MergeAction.ADDED)
        assert result.has_changes is True

    def test_summary(self) -> None:
        result = MergeResult(total_github_issues=3, total_org_headings=2)
        result.add_entry(1, "Issue 1", MergeAction.ADDED)
        result.add_entry(2, "Issue 2", MergeAction.UPDATED)

        summary = result.summary()
        assert "3 GitHub issues" in summary
        assert "2 Org headings" in summary
        assert "Added: 1" in summary
        assert "Updated: 1" in summary
