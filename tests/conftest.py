"""Pytest configuration and fixtures."""

from datetime import datetime
from typing import Any

import pytest

from gh_org_sync.models import (
    Comment,
    GitHubIssue,
    IssueState,
    Label,
    Milestone,
    OrgHeading,
    OrgTodoState,
    User,
)


@pytest.fixture
def sample_user() -> User:
    """Create a sample GitHub user."""
    return User(login="testuser", url="https://github.com/testuser")


@pytest.fixture
def sample_labels() -> list[Label]:
    """Create sample labels."""
    return [
        Label(name="bug", color="d73a4a"),
        Label(name="enhancement", color="a2eeef"),
    ]


@pytest.fixture
def sample_milestone() -> Milestone:
    """Create a sample milestone."""
    return Milestone(
        title="v1.0.0",
        number=1,
        state="open",
        due_on=datetime(2024, 6, 1),
    )


@pytest.fixture
def sample_comment(sample_user: User) -> Comment:
    """Create a sample comment."""
    return Comment(
        id=1,
        author=sample_user,
        body="This is a test comment.",
        created_at=datetime(2024, 1, 15, 10, 30),
        updated_at=datetime(2024, 1, 15, 10, 30),
    )


@pytest.fixture
def sample_issue(
    sample_user: User,
    sample_labels: list[Label],
    sample_milestone: Milestone,
    sample_comment: Comment,
) -> GitHubIssue:
    """Create a sample GitHub issue."""
    return GitHubIssue(
        number=123,
        title="Test Issue Title",
        body="This is the issue body.\n\nWith multiple paragraphs.",
        state=IssueState.OPEN,
        created_at=datetime(2024, 1, 10, 9, 0),
        updated_at=datetime(2024, 1, 15, 14, 30),
        author=sample_user,
        assignees=[sample_user],
        labels=sample_labels,
        milestone=sample_milestone,
        url="https://github.com/owner/repo/issues/123",
        comments=[sample_comment],
    )


@pytest.fixture
def sample_closed_issue(sample_user: User) -> GitHubIssue:
    """Create a sample closed issue."""
    return GitHubIssue(
        number=124,
        title="Closed Issue",
        body="This issue is closed.",
        state=IssueState.CLOSED,
        created_at=datetime(2024, 1, 5, 9, 0),
        updated_at=datetime(2024, 1, 12, 16, 0),
        closed_at=datetime(2024, 1, 12, 16, 0),
        author=sample_user,
        url="https://github.com/owner/repo/issues/124",
    )


@pytest.fixture
def sample_org_heading() -> OrgHeading:
    """Create a sample Org heading."""
    return OrgHeading(
        level=1,
        title="Test Heading",
        todo_state=OrgTodoState.TODO,
        tags=["LINK", "bug"],
        properties={
            "GITHUB_NUMBER": "123",
            "URL": "https://github.com/owner/repo/issues/123",
            "GITHUB_STATE": "open",
            "GITHUB_UPDATED": "2024-01-15T14:30:00",
        },
        content="Test content here.",
    )


@pytest.fixture
def sample_org_content() -> str:
    """Sample Org file content for parsing tests."""
    return """#+TITLE: GitHub Issues
#+DESCRIPTION: Test issues
#+STARTUP: overview

* TODO First Issue :LINK:bug:
:PROPERTIES:
:GITHUB_NUMBER: 1
:URL: https://github.com/owner/repo/issues/1
:GITHUB_STATE: open
:GITHUB_UPDATED: 2024-01-15T10:00:00
:END:

This is the first issue body.

** Comment by @user1 [2024-01-15 Mon 10:30]
First comment.

# --- End of GitHub synced content ---

User added notes here.

* DONE Second Issue :LINK:
:PROPERTIES:
:GITHUB_NUMBER: 2
:URL: https://github.com/owner/repo/issues/2
:GITHUB_STATE: closed
:GITHUB_UPDATED: 2024-01-14T16:00:00
:END:
CLOSED: [2024-01-14 Sun 16:00]

This issue was completed.

# --- End of GitHub synced content ---

* TODO User Task
User created this task manually.
"""
