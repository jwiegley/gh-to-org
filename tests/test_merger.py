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

        # Comments should be in children, not content
        children = headings[0].children
        assert len(children) == 2
        assert "First comment" in children[0].content
        assert "Second comment" in children[1].content
        assert "@commenter" in children[0].title

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

    def test_merge_preserves_custom_ordering(self, merger: OrgMerger) -> None:
        """Test that user's custom ordering of existing headings is preserved."""
        # Create GitHub issues in sorted order: 5, 10, 15
        issue_5 = GitHubIssue(
            number=5,
            title="Issue 5",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 5),
            updated_at=datetime(2024, 1, 6),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/5",
        )
        issue_10 = GitHubIssue(
            number=10,
            title="Issue 10",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 10),
            updated_at=datetime(2024, 1, 11),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/10",
        )
        issue_15 = GitHubIssue(
            number=15,
            title="Issue 15",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 15),
            updated_at=datetime(2024, 1, 16),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/15",
        )
        issue_20 = GitHubIssue(
            number=20,
            title="Issue 20",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 20),
            updated_at=datetime(2024, 1, 21),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/20",
        )

        # Create existing headings in CUSTOM order: 15, 5, user, 10
        # This simulates user reordering their org file
        heading_15 = OrgHeading(
            level=1,
            title="Issue 15",
            properties={
                "GITHUB_NUMBER": "15",
                "GITHUB_UPDATED": "2024-01-15T10:00:00",
            },
        )
        heading_5 = OrgHeading(
            level=1,
            title="Issue 5",
            properties={
                "GITHUB_NUMBER": "5",
                "GITHUB_UPDATED": "2024-01-05T10:00:00",
            },
        )
        user_heading = OrgHeading(
            level=1,
            title="My Custom Task",
            content="User created content",
        )
        heading_10 = OrgHeading(
            level=1,
            title="Issue 10",
            properties={
                "GITHUB_NUMBER": "10",
                "GITHUB_UPDATED": "2024-01-10T10:00:00",
            },
        )

        # Merge with GitHub issues
        headings, result = merger.merge(
            [issue_5, issue_10, issue_15, issue_20],
            [heading_15, heading_5, user_heading, heading_10],
        )

        # Verify order is preserved: 15, 5, user, 10, NEW (20)
        assert len(headings) == 5
        assert headings[0].github_number == 15
        assert headings[0].title == "Issue 15"
        assert headings[1].github_number == 5
        assert headings[1].title == "Issue 5"
        assert headings[2].github_number is None
        assert headings[2].title == "My Custom Task"
        assert headings[3].github_number == 10
        assert headings[3].title == "Issue 10"
        assert headings[4].github_number == 20
        assert headings[4].title == "Issue 20"

        # Verify statistics
        assert result.added == 1  # issue 20 is new
        assert result.updated == 3  # issues 5, 10, 15 updated
        assert result.preserved == 1  # user heading

    def test_merge_new_issues_appended_sorted(self, merger: OrgMerger) -> None:
        """Test that new issues are appended at the end in sorted order."""
        # Existing heading with issue 10
        existing = OrgHeading(
            level=1,
            title="Issue 10",
            properties={
                "GITHUB_NUMBER": "10",
                "GITHUB_UPDATED": "2024-01-10T10:00:00",
            },
        )

        # GitHub has issues 10 (existing), 25, 15, 5 (all new, unsorted)
        issue_10 = GitHubIssue(
            number=10,
            title="Issue 10 Updated",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 10),
            updated_at=datetime(2024, 1, 11),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/10",
        )
        issue_25 = GitHubIssue(
            number=25,
            title="Issue 25",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 25),
            updated_at=datetime(2024, 1, 26),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/25",
        )
        issue_15 = GitHubIssue(
            number=15,
            title="Issue 15",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 15),
            updated_at=datetime(2024, 1, 16),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/15",
        )
        issue_5 = GitHubIssue(
            number=5,
            title="Issue 5",
            state=IssueState.OPEN,
            created_at=datetime(2024, 1, 5),
            updated_at=datetime(2024, 1, 6),
            author=User(login="author"),
            url="https://github.com/owner/repo/issues/5",
        )

        # Merge
        headings, result = merger.merge(
            [issue_10, issue_25, issue_15, issue_5],
            [existing],
        )

        # Verify order: existing (10) first, then new issues sorted (5, 15, 25)
        assert len(headings) == 4
        assert headings[0].github_number == 10
        assert headings[0].title == "Issue 10 Updated"
        assert headings[1].github_number == 5
        assert headings[2].github_number == 15
        assert headings[3].github_number == 25

        # Verify statistics
        assert result.added == 3
        assert result.updated == 1
