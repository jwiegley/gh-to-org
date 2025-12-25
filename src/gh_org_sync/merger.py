"""
Intelligent merge logic for GitHub issues and Org-mode headings.

This module provides the core merge algorithm that:
- Updates existing entries from GitHub while preserving user additions
- Adds new issues that don't exist in the Org file
- Preserves user-created headings that aren't linked to GitHub
- Maintains proper ordering
"""

import logging
import re

from .models import (
    GitHubIssue,
    MergeAction,
    MergeResult,
    OrgHeading,
    OrgTodoState,
)
from .org_writer import (
    OrgWriter,
    escape_org_content,
    format_timestamp,
)

logger = logging.getLogger(__name__)


def _normalize_for_comparison(text: str) -> str:
    """
    Normalize text for comparison to ignore whitespace-only differences.

    - Normalizes line endings (CRLF/CR -> LF)
    - Strips trailing whitespace from each line
    - Collapses multiple spaces on heading lines (for tag alignment)
    - Removes leading/trailing blank lines
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Process each line
    normalized_lines: list[str] = []
    for line in text.split("\n"):
        line = line.rstrip()
        # Collapse multiple spaces on heading lines (tag alignment normalization)
        if line.startswith("*"):
            line = re.sub(r"  +", " ", line)
        normalized_lines.append(line)
    # Join and strip leading/trailing blank lines
    return "\n".join(normalized_lines).strip()


class OrgMerger:
    """
    Merges GitHub issues with existing Org-mode content.

    The merge strategy preserves user additions while updating
    GitHub-sourced content. Key principles:

    1. Issues are matched by GITHUB_NUMBER property
    2. GitHub-managed fields are updated (title, state, body, comments)
    3. User-added content after the sync marker is preserved
    4. User-added properties (non-GITHUB_*) are preserved
    5. User-added tags are preserved
    6. Headings without GITHUB_NUMBER are left untouched
    """

    # Marker that separates synced content from user additions
    SYNC_MARKER = "# --- End of GitHub synced content ---"

    def __init__(self, add_link_tag: bool = True) -> None:
        """
        Initialize the merger.

        Args:
            add_link_tag: Whether to add :LINK: tag to issues
        """
        self.add_link_tag = add_link_tag
        self.writer = OrgWriter(add_link_tag=add_link_tag)

    def merge(
        self,
        github_issues: list[GitHubIssue],
        existing_headings: list[OrgHeading],
    ) -> tuple[list[OrgHeading], MergeResult]:
        """
        Merge GitHub issues with existing Org headings.

        Preserves the order of existing headings. For each existing heading:
        - If it has a GITHUB_NUMBER and a matching issue exists, merge in place
        - If it has no GITHUB_NUMBER (user-created), preserve as-is
        - If it has a GITHUB_NUMBER but no matching issue, preserve as-is

        New issues (not in existing file) are appended at the end.

        Args:
            github_issues: List of issues from GitHub
            existing_headings: List of headings from Org file

        Returns:
            Tuple of (merged headings list, merge result statistics)
        """
        result = MergeResult(
            total_github_issues=len(github_issues),
            total_org_headings=len(existing_headings),
        )

        # Build index of GitHub issues by number for efficient lookup
        issue_index: dict[int, GitHubIssue] = {
            issue.number: issue for issue in github_issues
        }

        # Track which GitHub issues have been processed
        processed_issue_numbers: set[int] = set()

        # Process existing headings in order, merging with GitHub data where applicable
        merged_headings: list[OrgHeading] = []

        for heading in existing_headings:
            gh_num = heading.github_number

            if gh_num is None:
                # User-created heading with no GitHub link - preserve as-is
                merged_headings.append(heading)
                result.preserved += 1
            elif gh_num in issue_index:
                # Existing heading with matching GitHub issue - merge in place
                issue = issue_index[gh_num]
                updated, action = self._merge_heading(issue, heading)
                merged_headings.append(updated)
                processed_issue_numbers.add(gh_num)
                result.add_entry(
                    issue_number=issue.number,
                    title=issue.title,
                    action=action,
                    details=(
                        self._describe_changes(issue, heading)
                        if action == MergeAction.UPDATED
                        else None
                    ),
                )
            else:
                # Existing heading with GITHUB_NUMBER but no matching issue
                # (might be closed/deleted issue) - preserve as-is
                merged_headings.append(heading)
                result.preserved += 1

        # Append new issues that weren't in the existing file
        # Sort new issues by number for consistent ordering of additions
        new_issues = [
            issue for issue in github_issues
            if issue.number not in processed_issue_numbers
        ]
        for issue in sorted(new_issues, key=lambda i: i.number):
            new_heading = self._issue_to_heading(issue)
            merged_headings.append(new_heading)
            result.add_entry(
                issue_number=issue.number,
                title=issue.title,
                action=MergeAction.ADDED,
            )

        return merged_headings, result

    def _merge_heading(
        self,
        issue: GitHubIssue,
        existing: OrgHeading,
    ) -> tuple[OrgHeading, MergeAction]:
        """
        Merge a GitHub issue into an existing heading.

        Preserves user additions while updating GitHub content.

        Args:
            issue: GitHub issue with latest data
            existing: Existing Org heading

        Returns:
            Tuple of (merged heading, action taken)
        """
        # Check if update is needed
        if not self._needs_update(issue, existing):
            return existing, MergeAction.UNCHANGED

        # Create new heading with GitHub data
        # Note: raw_text is not set (defaults to None) since heading is modified
        merged = OrgHeading(
            level=existing.level,
            title=issue.title,
            todo_state=OrgTodoState.DONE if issue.state.value == "closed" else OrgTodoState.TODO,
            tags=self._merge_tags(issue, existing),
            properties=self._merge_properties(issue, existing),
            content=self._merge_content(issue, existing),
            children=self._merge_children(issue, existing),
            source_line=existing.source_line,
            raw_text=None,  # Clear raw_text since heading has been modified
        )

        # Compare normalized rendered output to detect whitespace-only changes
        existing_text = _normalize_for_comparison(self.writer.format_heading(existing))
        merged_text = _normalize_for_comparison(self.writer.format_heading(merged))

        if existing_text == merged_text:
            return existing, MergeAction.UNCHANGED

        return merged, MergeAction.UPDATED

    def _needs_update(self, issue: GitHubIssue, existing: OrgHeading) -> bool:
        """Check if the heading needs to be updated from GitHub."""
        # Compare GitHub updated timestamp
        existing_updated = existing.github_updated
        if existing_updated is None:
            return True

        # If GitHub issue is newer, update is needed
        # Compare at minute precision since Org format doesn't store seconds
        github_minute = issue.updated_at.replace(second=0, microsecond=0)
        existing_minute = existing_updated.replace(second=0, microsecond=0)
        if github_minute > existing_minute:
            return True

        # Also check for state changes
        existing_state = existing.properties.get("GITHUB_STATE", "").lower()
        return existing_state != issue.state.value

    def _merge_tags(
        self,
        issue: GitHubIssue,
        existing: OrgHeading,
    ) -> list[str]:
        """
        Merge tags from GitHub and existing heading.

        GitHub labels become tags, but user-added tags are preserved.
        """
        # Start with LINK tag if enabled
        tags: list[str] = []
        if self.add_link_tag:
            tags.append("LINK")

        # Add GitHub labels as tags
        for label in issue.label_names:
            clean_tag = re.sub(r"[:\s]+", "_", label.strip()).strip("_")
            if clean_tag and clean_tag not in tags:
                tags.append(clean_tag)

        # Preserve user-added tags (not from GitHub labels and not LINK)
        github_label_tags = {
            re.sub(r"[:\s]+", "_", lbl.strip()).strip("_") for lbl in issue.label_names
        }
        for tag in existing.tags:
            if tag.upper() != "LINK" and tag not in github_label_tags and tag not in tags:
                tags.append(tag)

        return tags

    def _merge_properties(
        self,
        issue: GitHubIssue,
        existing: OrgHeading,
    ) -> dict[str, str]:
        """
        Merge properties from GitHub and existing heading.

        GitHub properties are updated, user properties preserved.
        """
        # Start with user properties (non-GITHUB_* prefix)
        github_managed = ("URL", "CREATED", "AUTHOR", "ASSIGNEES", "MILESTONE", "CLOSED")
        properties: dict[str, str] = {}
        for key, value in existing.properties.items():
            if not key.startswith("GITHUB_") and key not in github_managed:
                properties[key] = value

        # Add/update GitHub properties
        properties["GITHUB_NUMBER"] = str(issue.number)
        properties["URL"] = str(issue.url)
        properties["GITHUB_STATE"] = issue.state.value
        properties["GITHUB_UPDATED"] = format_timestamp(issue.updated_at)
        properties["CREATED"] = format_timestamp(issue.created_at)
        properties["AUTHOR"] = issue.author.login

        if issue.assignee_logins:
            properties["ASSIGNEES"] = ", ".join(issue.assignee_logins)
        if issue.milestone:
            properties["MILESTONE"] = issue.milestone.title
        if issue.closed_at:
            properties["CLOSED"] = format_timestamp(issue.closed_at)

        return properties

    def _merge_content(
        self,
        issue: GitHubIssue,
        existing: OrgHeading,
    ) -> str:
        """
        Merge content from GitHub and existing heading.

        GitHub body is updated, user additions preserved.
        Comments are handled separately via children, not in content.
        """
        parts: list[str] = []

        # GitHub body only - comments are handled as children
        if issue.body:
            parts.append(escape_org_content(issue.body.strip()))

        # Extract and preserve user additions (content after sync marker)
        user_content = self._extract_user_content(existing.content)
        if user_content:
            parts.append("")
            parts.append(user_content)

        return "\n".join(parts).rstrip()

    def _extract_user_content(self, content: str) -> str:
        """Extract user-added content after the sync marker."""
        if self.SYNC_MARKER not in content:
            # No marker, check if there's content that looks user-added
            # For legacy entries, we can't distinguish, so preserve nothing
            return ""

        # Split on marker and take content after it
        parts = content.split(self.SYNC_MARKER, 1)
        if len(parts) > 1:
            return parts[1].strip()

        return ""

    def _merge_children(
        self,
        issue: GitHubIssue,
        existing: OrgHeading,
    ) -> list[OrgHeading]:
        """
        Merge children from GitHub comments and existing heading.

        GitHub comments become children, user-added children are preserved.
        """
        children: list[OrgHeading] = []

        # Build comment children from GitHub
        if issue.comments:
            for comment in sorted(issue.comments, key=lambda c: c.created_at):
                timestamp = format_timestamp(comment.created_at)
                author = comment.author.login
                comment_content = ""
                if comment.body:
                    comment_content = escape_org_content(comment.body.strip())
                children.append(OrgHeading(
                    level=existing.level + 1,
                    title=f"Comment by @{author} {timestamp}",
                    content=comment_content,
                ))

        # Preserve user-added children (not comments)
        for child in existing.children:
            if not child.title.startswith("Comment by @"):
                children.append(child)

        return children

    def _issue_to_heading(self, issue: GitHubIssue, level: int = 1) -> OrgHeading:
        """Convert a GitHub issue to a new OrgHeading."""
        # Build tags
        tags: list[str] = []
        if self.add_link_tag:
            tags.append("LINK")
        for label in issue.label_names:
            clean_tag = re.sub(r"[:\s]+", "_", label.strip()).strip("_")
            if clean_tag:
                tags.append(clean_tag)

        # Build properties
        properties: dict[str, str] = {
            "GITHUB_NUMBER": str(issue.number),
            "URL": str(issue.url),
            "GITHUB_STATE": issue.state.value,
            "GITHUB_UPDATED": format_timestamp(issue.updated_at),
            "CREATED": format_timestamp(issue.created_at),
            "AUTHOR": issue.author.login,
        }

        if issue.assignee_logins:
            properties["ASSIGNEES"] = ", ".join(issue.assignee_logins)
        if issue.milestone:
            properties["MILESTONE"] = issue.milestone.title
        if issue.closed_at:
            properties["CLOSED"] = format_timestamp(issue.closed_at)

        # Build content (body only - comments are children)
        content = ""
        if issue.body:
            content = escape_org_content(issue.body.strip())

        # Build comment children
        children: list[OrgHeading] = []
        if issue.comments:
            for comment in sorted(issue.comments, key=lambda c: c.created_at):
                timestamp = format_timestamp(comment.created_at)
                author = comment.author.login
                comment_content = ""
                if comment.body:
                    comment_content = escape_org_content(comment.body.strip())
                children.append(OrgHeading(
                    level=level + 1,
                    title=f"Comment by @{author} {timestamp}",
                    content=comment_content,
                ))

        return OrgHeading(
            level=level,
            title=issue.title,
            todo_state=OrgTodoState.DONE if issue.state.value == "closed" else OrgTodoState.TODO,
            tags=tags,
            properties=properties,
            content=content,
            children=children,
        )

    def _describe_changes(self, issue: GitHubIssue, existing: OrgHeading) -> str:
        """Generate a description of what changed."""
        changes: list[str] = []

        # Check title
        if issue.title != existing.title:
            changes.append("title")

        # Check state
        existing_state = existing.properties.get("GITHUB_STATE", "").lower()
        if existing_state != issue.state.value:
            changes.append(f"state ({existing_state} -> {issue.state.value})")

        # Check for new comments
        existing_comment_count = existing.properties.get("COMMENTS", "0")
        try:
            if int(existing_comment_count) < len(issue.comments):
                changes.append("new comments")
        except ValueError:
            pass

        if changes:
            return ", ".join(changes)
        return "content updated"
