"""Tests for merge logic."""

from datetime import datetime

import pytest

from gh_org_sync.merger import OrgMerger
from gh_org_sync.models import (
    Comment,
    GitHubIssue,
    IssueState,
    Label,
    MergeAction,
    OrgHeading,
    OrgTodoState,
    User,
)


class TestOrgMerger:
    """Tests for OrgMerger class."""

    @pytest.fixture
    def merger(self) -> OrgMerger:
        return OrgMerger()

    @pytest.fixture
    def github_issue(self) -> GitHubIssue:
        return GitHubIssue(
            number=1,
            title="Test Issue",
            body="Issue body content.",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 10),
            updated_at=datetime(2024, 1, 15, 12, 0),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/1",
        )

    @pytest.fixture
    def existing_heading(self) -> OrgHeading:
        return OrgHeading(
            level=1,
            title="Test Issue",
            todo_state=OrgTodoState.TODO,
            tags=["LINK"],
            properties={
                "GITHUB_NUMBER": "1",
                "URL": "https://github.com/owner/repo/issues/1",
                "GITHUB_STATE": "open",
                "GITHUB_UPDATED": "2024-01-14T10:00:00",
            },
            content="Old body content.\n\n# --- End of GitHub synced content ---\n\nUser notes here.",
        )

    def test_merge_adds_new_issue(
        self,
        merger: OrgMerger,
        github_issue: GitHubIssue,
    ) -> None:
        """Test that new issues are added."""
        headings, result = merger.merge([github_issue], [])

        assert len(headings) == 1
        assert result.added == 1
        assert result.updated == 0
        assert headings[0].title == "Test Issue"
        assert headings[0].github_number == 1

    def test_merge_updates_existing_issue(
        self,
        merger: OrgMerger,
        github_issue: GitHubIssue,
        existing_heading: OrgHeading,
    ) -> None:
        """Test that existing issues are updated."""
        headings, result = merger.merge([github_issue], [existing_heading])

        assert len(headings) == 1
        assert result.updated == 1
        assert result.added == 0
        # User content should be preserved
        assert "User notes here" in headings[0].content

    def test_merge_preserves_user_heading(self, merger: OrgMerger) -> None:
        """Test that user-created headings are preserved."""
        user_heading = OrgHeading(
            level=1,
            title="My Task",
            todo_state=OrgTodoState.TODO,
            content="User created task.",
        )

        headings, result = merger.merge([], [user_heading])

        assert len(headings) == 1
        assert result.preserved == 1
        assert headings[0].title == "My Task"

    def test_merge_preserves_user_tags(
        self,
        merger: OrgMerger,
        github_issue: GitHubIssue,
    ) -> None:
        """Test that user-added tags are preserved."""
        existing = OrgHeading(
            level=1,
            title="Test Issue",
            todo_state=OrgTodoState.TODO,
            tags=["LINK", "user_tag", "custom"],
            properties={
                "GITHUB_NUMBER": "1",
                "URL": "https://github.com/owner/repo/issues/1",
                "GITHUB_STATE": "open",
                "GITHUB_UPDATED": "2024-01-10T10:00:00",
            },
        )

        headings, result = merger.merge([github_issue], [existing])

        assert "user_tag" in headings[0].tags
        assert "custom" in headings[0].tags

    def test_merge_updates_state(self, merger: OrgMerger) -> None:
        """Test that state changes are reflected."""
        closed_issue = GitHubIssue(
            number=1,
            title="Test Issue",
            state=IssueState.CLOSED,
            created_at=datetime(2024, 1, 10),
            updated_at=datetime(2024, 1, 15),
            closed_at=datetime(2024, 1, 15),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/1",
        )

        existing = OrgHeading(
            level=1,
            title="Test Issue",
            todo_state=OrgTodoState.TODO,
            properties={
                "GITHUB_NUMBER": "1",
                "GITHUB_STATE": "open",
                "GITHUB_UPDATED": "2024-01-10T10:00:00",
            },
        )

        headings, result = merger.merge([closed_issue], [existing])

        assert headings[0].todo_state == OrgTodoState.DONE
        assert result.updated == 1

    def test_merge_with_comments(self, merger: OrgMerger) -> None:
        """Test that comments are included."""
        issue = GitHubIssue(
            number=1,
            title="Issue with comments",
            body="Body",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 10),
            updated_at=datetime(2024, 1, 15),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/1",
            comments=[
                Comment(
                    id=1,
                    author=User(login="commenter"),
                    body="First comment",
                    created_at=datetime(2024, 1, 12),
                ),
                Comment(
                    id=2,
                    author=User(login="author"),
                    body="Second comment",
                    created_at=datetime(2024, 1, 14),
                ),
            ],
        )

        headings, result = merger.merge([issue], [])

        content = headings[0].content
        assert "First comment" in content
        assert "Second comment" in content
        assert "@commenter" in content

    def test_merge_result_statistics(
        self,
        merger: OrgMerger,
        github_issue: GitHubIssue,
        existing_heading: OrgHeading,
    ) -> None:
        """Test that merge result statistics are accurate."""
        user_heading = OrgHeading(level=1, title="User Task")

        new_issue = GitHubIssue(
            number=2,
            title="New Issue",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 10),
            updated_at=datetime(2024, 1, 10),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/2",
        )

        headings, result = merger.merge(
            [github_issue, new_issue],
            [existing_heading, user_heading],
        )

        assert result.total_github_issues == 2
        assert result.total_org_headings == 2
        assert result.added == 1  # new_issue
        assert result.updated == 1  # github_issue
        assert result.preserved == 1  # user_heading
