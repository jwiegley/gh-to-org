"""
Org-mode file writer.

This module handles writing Org-mode formatted content to files,
with proper escaping, formatting, and atomic write operations.
"""

import logging
import re
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from .exceptions import OrgBackupError, OrgWriteError
from .models import GitHubIssue, OrgHeading

logger = logging.getLogger(__name__)


def escape_org_content(text: str) -> str:
    """
    Escape text for safe inclusion in Org-mode content.

    Handles lines starting with special characters that would be
    interpreted as Org-mode syntax.

    Args:
        text: Raw text to escape

    Returns:
        Escaped text safe for Org-mode
    """
    if not text:
        return ""

    lines = text.split("\n")
    escaped_lines: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if not stripped:
            escaped_lines.append(line)
            continue

        indent = line[: len(line) - len(stripped)]
        needs_escape = False

        # Check for special line-start patterns
        if stripped.startswith(("*", "#")):
            needs_escape = True
        elif stripped.startswith(":") and ":" in stripped[1:]:
            # Check if it looks like a property :NAME:
            colon_pos = stripped.index(":", 1)
            potential_keyword = stripped[1:colon_pos]
            if potential_keyword and re.match(
                r"^[A-Za-z_][A-Za-z0-9_-]*$", potential_keyword
            ):
                needs_escape = True

        if needs_escape:
            line = indent + ", " + stripped

        # Escape Org-mode link brackets
        line = line.replace("[[", r"\[\[")
        line = line.replace("]]", r"\]\]")

        escaped_lines.append(line)

    return "\n".join(escaped_lines)


def format_timestamp(dt: datetime, active: bool = False) -> str:
    """
    Format datetime as Org-mode timestamp.

    Args:
        dt: Datetime to format
        active: If True, use <> for active timestamps (agenda-visible)

    Returns:
        Formatted timestamp like [2024-01-15 Mon 10:30]
    """
    bracket = ("<", ">") if active else ("[", "]")
    return f"{bracket[0]}{dt.strftime('%Y-%m-%d %a %H:%M')}{bracket[1]}"


def format_tags(tags: list[str], include_link: bool = True) -> str:
    """
    Format tags for Org-mode heading line.

    Args:
        tags: List of tag strings
        include_link: If True, add :LINK: tag

    Returns:
        Formatted tag string like :LINK:bug:urgent:
    """
    all_tags: list[str] = []

    if include_link:
        all_tags.append("LINK")

    for tag in tags:
        if not tag:
            continue
        # Clean tag: replace invalid characters with underscores
        clean_tag = re.sub(r"[:\s]+", "_", tag.strip())
        clean_tag = clean_tag.strip("_")
        if clean_tag:
            all_tags.append(clean_tag)

    if not all_tags:
        return ""

    return ":" + ":".join(all_tags) + ":"


def format_properties(
    properties: Mapping[str, str | int | datetime | None],
    indent: str = "",
) -> str:
    """
    Format properties as Org-mode PROPERTIES drawer.

    Args:
        properties: Dictionary of property name -> value
        indent: Indentation for each line

    Returns:
        Formatted properties drawer
    """
    if not properties:
        return ""

    lines = [f"{indent}:PROPERTIES:"]

    # Filter out None values and find max key length
    valid_props = {
        k: v for k, v in properties.items() if v is not None and str(v).strip()
    }

    if not valid_props:
        return ""

    max_len = max(len(str(k)) for k in valid_props)

    for key, value in valid_props.items():
        # Format value based on type
        value_str = value.isoformat() if isinstance(value, datetime) else str(value)

        key_upper = str(key).upper()
        padding = " " * (max_len - len(key_upper) + 1)
        lines.append(f"{indent}:{key_upper}:{padding}{value_str}")

    lines.append(f"{indent}:END:")

    return "\n".join(lines)


class OrgWriter:
    """
    Writer for Org-mode files.

    Provides methods to format and write Org-mode content,
    with support for atomic writes and backups.
    """

    # Marker for synced content boundary
    SYNC_MARKER = "# --- End of GitHub synced content ---"

    def __init__(self, add_link_tag: bool = True) -> None:
        """
        Initialize the writer.

        Args:
            add_link_tag: Whether to add :LINK: tag to issues with URLs
        """
        self.add_link_tag = add_link_tag

    def format_file_header(
        self,
        title: str,
        repo: str,
        description: str = "",
    ) -> str:
        """
        Format Org-mode file header.

        Args:
            title: File title
            repo: Repository name
            description: Optional description

        Returns:
            Formatted header
        """
        desc = description if description else f"GitHub issues synced from {repo}"
        lines = [
            f"#+TITLE: {title}",
            f"#+DESCRIPTION: {desc}",
            "#+STARTUP: overview",
            f"#+SYNC_REPO: {repo}",
            f"#+SYNC_TIME: {datetime.now(UTC).isoformat()}",
            "",
        ]
        return "\n".join(lines)

    def format_issue_heading(self, issue: GitHubIssue, level: int = 1) -> str:
        """
        Format a GitHub issue as an Org-mode heading.

        Args:
            issue: GitHub issue to format
            level: Heading level (1 = *, 2 = **, etc.)

        Returns:
            Formatted Org-mode heading with properties and content
        """
        lines: list[str] = []

        # Heading line
        stars = "*" * level
        todo_state = "DONE" if issue.state.value == "closed" else "TODO"
        tags = format_tags(issue.label_names, include_link=self.add_link_tag)

        if tags:
            heading = f"{stars} {todo_state} {issue.title} {tags}"
        else:
            heading = f"{stars} {todo_state} {issue.title}"

        lines.append(heading)

        # Properties drawer
        properties: dict[str, str | int | datetime | None] = {
            "GITHUB_NUMBER": issue.number,
            "URL": str(issue.url),
            "GITHUB_STATE": issue.state.value,
            "GITHUB_UPDATED": issue.updated_at,
            "CREATED": issue.created_at,
            "AUTHOR": issue.author.login,
        }

        if issue.assignee_logins:
            properties["ASSIGNEES"] = ", ".join(issue.assignee_logins)
        if issue.milestone:
            properties["MILESTONE"] = issue.milestone.title
        if issue.closed_at:
            properties["CLOSED"] = issue.closed_at

        props_text = format_properties(properties)
        if props_text:
            lines.append(props_text)

        # CLOSED timestamp for done items (Org convention)
        if issue.state.value == "closed" and issue.closed_at:
            lines.append(f"CLOSED: {format_timestamp(issue.closed_at)}")

        # Body
        if issue.body:
            lines.append("")
            escaped_body = escape_org_content(issue.body.strip())
            lines.append(escaped_body)

        # Comments as sub-headings
        if issue.comments:
            lines.append("")
            comment_stars = "*" * (level + 1)

            for comment in sorted(issue.comments, key=lambda c: c.created_at):
                timestamp = format_timestamp(comment.created_at)
                lines.append(f"{comment_stars} Comment by @{comment.author.login} {timestamp}")

                if comment.body:
                    escaped_comment = escape_org_content(comment.body.strip())
                    lines.append(escaped_comment)
                lines.append("")

        # Add sync marker
        lines.append("")
        lines.append(self.SYNC_MARKER)

        return "\n".join(lines)

    def format_heading(self, heading: OrgHeading) -> str:
        """
        Format an OrgHeading back to Org-mode text.

        Args:
            heading: OrgHeading to format

        Returns:
            Formatted Org-mode text
        """
        lines: list[str] = []

        # Heading line
        stars = "*" * heading.level
        parts = [stars]

        if heading.todo_state:
            parts.append(heading.todo_state.value)

        parts.append(heading.title)

        if heading.tags:
            parts.append(":" + ":".join(heading.tags) + ":")

        lines.append(" ".join(parts))

        # Properties drawer
        if heading.properties:
            props_text = format_properties(heading.properties)
            if props_text:
                lines.append(props_text)

        # Content
        if heading.content:
            lines.append(heading.content)

        # Children
        for child in heading.children:
            lines.append("")
            lines.append(self.format_heading(child))

        return "\n".join(lines)

    def write_file(
        self,
        headings: list[OrgHeading],
        path: Path | str,
        header: str = "",
        backup: bool = True,
    ) -> None:
        """
        Write headings to an Org-mode file.

        Uses atomic write (write to temp file, then rename) for safety.

        Args:
            headings: List of headings to write
            path: Output file path
            header: Optional file header
            backup: If True, create backup before overwriting

        Raises:
            OrgWriteError: If write fails
            OrgBackupError: If backup fails
        """
        path = Path(path)

        # Create backup if file exists
        if backup and path.exists():
            backup_path = path.with_suffix(path.suffix + ".bak")
            try:
                shutil.copy2(path, backup_path)
                logger.info(f"Created backup: {backup_path}")
            except OSError as e:
                raise OrgBackupError(str(path), str(e)) from e

        # Build content
        content_parts: list[str] = []

        if header:
            content_parts.append(header)

        for heading in headings:
            content_parts.append(self.format_heading(heading))
            content_parts.append("")  # Blank line between top-level headings

        content = "\n".join(content_parts)

        # Ensure single trailing newline
        content = content.rstrip() + "\n"

        # Atomic write
        temp_path = path.with_suffix(path.suffix + ".tmp")

        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file
            temp_path.write_text(content, encoding="utf-8")

            # Rename to final location
            temp_path.replace(path)

            logger.info(f"Wrote {len(headings)} headings to {path}")

        except OSError as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise OrgWriteError(str(path), str(e)) from e

    def write_issues(
        self,
        issues: list[GitHubIssue],
        path: Path | str,
        repo: str,
        backup: bool = True,
    ) -> None:
        """
        Write GitHub issues directly to an Org file.

        This is a convenience method for initial sync. For updates,
        use the merger to preserve user content.

        Args:
            issues: List of GitHub issues
            path: Output file path
            repo: Repository name for header
            backup: Whether to create backup
        """
        path = Path(path)

        # Build content
        content_parts: list[str] = []

        # Header
        content_parts.append(self.format_file_header(f"GitHub Issues: {repo}", repo))

        # Issues
        for issue in sorted(issues, key=lambda i: i.number):
            content_parts.append(self.format_issue_heading(issue))
            content_parts.append("")

        content = "\n".join(content_parts)
        content = content.rstrip() + "\n"

        # Create backup if file exists
        if backup and path.exists():
            backup_path = path.with_suffix(path.suffix + ".bak")
            try:
                shutil.copy2(path, backup_path)
                logger.info(f"Created backup: {backup_path}")
            except OSError as e:
                raise OrgBackupError(str(path), str(e)) from e

        # Write atomically
        temp_path = path.with_suffix(path.suffix + ".tmp")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
            logger.info(f"Wrote {len(issues)} issues to {path}")
        except OSError as e:
            if temp_path.exists():
                temp_path.unlink()
            raise OrgWriteError(str(path), str(e)) from e
