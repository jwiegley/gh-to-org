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


def normalize_line_endings(text: str) -> str:
    """
    Normalize line endings to Unix-style (LF only).

    Converts Windows (CRLF) and old Mac (CR) line endings to Unix (LF).

    Args:
        text: Text with potentially mixed line endings

    Returns:
        Text with only LF line endings
    """
    # First convert CRLF to LF, then standalone CR to LF
    return text.replace("\r\n", "\n").replace("\r", "\n")


def markdown_to_org(text: str) -> str:
    """
    Convert Markdown markup to Org-mode equivalents.

    Handles common Markdown patterns:
    - [text](url) → [[url][text]]
    - **bold** → *bold*
    - *italic* → /italic/
    - _italic_ → /italic/
    - `code` → =code=
    - ~~strikethrough~~ → +strikethrough+
    - ```code blocks``` → #+BEGIN_SRC / #+END_SRC

    Args:
        text: Text with Markdown markup

    Returns:
        Text with Org-mode markup
    """
    if not text:
        return ""

    # Normalize line endings first
    text = normalize_line_endings(text)

    # Convert fenced code blocks (```lang ... ```) to Org source blocks
    # Must be done before other conversions to avoid mangling code content
    def convert_code_block(match: re.Match[str]) -> str:
        lang = match.group(1) or ""
        code = match.group(2)
        if lang:
            return f"#+BEGIN_SRC {lang}\n{code}#+END_SRC"
        return f"#+BEGIN_SRC\n{code}#+END_SRC"

    text = re.sub(
        r"```(\w*)\n(.*?)```",
        convert_code_block,
        text,
        flags=re.DOTALL,
    )

    # Convert Markdown links [text](url) to Org links [[url][text]]
    # Be careful not to match already-escaped brackets
    text = re.sub(
        r"(?<!\[)\[([^\]]+)\]\(([^)]+)\)",
        r"[[\2][\1]]",
        text,
    )

    # Convert inline code `code` to Org verbatim =code=
    # Use non-greedy match and avoid matching code that spans lines
    text = re.sub(r"`([^`\n]+)`", r"=\1=", text)

    # Convert bold **text** to Org *text*
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)

    # Convert bold __text__ to Org *text*
    text = re.sub(r"__([^_]+)__", r"*\1*", text)

    # Convert italic *text* to Org /text/ (single asterisks not already bold)
    # This is tricky - we need to avoid matching list items
    # Only convert if preceded by whitespace or start of line
    text = re.sub(r"(?<=\s)\*([^*\n]+)\*(?=\s|$|[.,;:!?])", r"/\1/", text)

    # Convert italic _text_ to Org /text/
    # Only match word-bounded underscores
    text = re.sub(r"(?<=\s)_([^_\n]+)_(?=\s|$|[.,;:!?])", r"/\1/", text)

    # Convert strikethrough ~~text~~ to Org +text+
    text = re.sub(r"~~([^~]+)~~", r"+\1+", text)

    # Convert blockquotes > text to Org-mode style
    # Multi-line blockquotes become #+BEGIN_QUOTE blocks
    lines = text.split("\n")
    result_lines: list[str] = []
    in_blockquote = False

    for line in lines:
        if line.startswith("> "):
            if not in_blockquote:
                result_lines.append("#+BEGIN_QUOTE")
                in_blockquote = True
            result_lines.append(line[2:])  # Remove "> " prefix
        elif line.startswith(">"):
            if not in_blockquote:
                result_lines.append("#+BEGIN_QUOTE")
                in_blockquote = True
            result_lines.append(line[1:])  # Remove ">" prefix
        else:
            if in_blockquote:
                result_lines.append("#+END_QUOTE")
                in_blockquote = False
            result_lines.append(line)

    if in_blockquote:
        result_lines.append("#+END_QUOTE")

    return "\n".join(result_lines)


def escape_org_content(text: str) -> str:
    """
    Convert Markdown to Org-mode and escape special line-start patterns.

    This function:
    1. Normalizes line endings (removes ^M / CR characters)
    2. Converts Markdown markup to Org-mode equivalents
    3. Escapes lines starting with special characters that would be
       interpreted as Org-mode syntax

    Args:
        text: Raw text (possibly with Markdown) to process

    Returns:
        Text with Org-mode markup, safe for inclusion in Org content
    """
    if not text:
        return ""

    # First convert Markdown to Org-mode (also normalizes line endings)
    text = markdown_to_org(text)

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
        # Escape asterisks that aren't part of Org bold markup
        if stripped.startswith("*") and not re.match(r"^\*[^*\s].*[^*\s]\*", stripped):
            # Looks like a heading marker, not bold text
            if not stripped.startswith("*") or len(stripped) == 1 or stripped[1] == " ":
                needs_escape = True
        # Escape hash that could look like Org keywords
        elif stripped.startswith("#") and not stripped.startswith("#+"):
            needs_escape = True
        elif stripped.startswith(":") and ":" in stripped[1:]:
            # Check if it looks like a property :NAME:
            colon_pos = stripped.index(":", 1)
            potential_keyword = stripped[1:colon_pos]
            if potential_keyword and re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", potential_keyword):
                needs_escape = True

        if needs_escape:
            line = indent + ", " + stripped

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
    target_column: int = 11,
) -> str:
    """
    Format properties as Org-mode PROPERTIES drawer.

    Args:
        properties: Dictionary of property name -> value
        indent: Indentation for each line
        target_column: Column at which values should start (1-indexed).
                       Properties longer than this get a single space.

    Returns:
        Formatted properties drawer
    """
    if not properties:
        return ""

    lines = [f"{indent}:PROPERTIES:"]

    # Filter out None values
    valid_props = {k: v for k, v in properties.items() if v is not None and str(v).strip()}

    if not valid_props:
        return ""

    for key, value in sorted(valid_props.items()):
        # Format value based on type (use Org-mode timestamp for datetime)
        value_str = format_timestamp(value) if isinstance(value, datetime) else str(value)

        key_upper = str(key).upper()
        # Property prefix is ":NAME:" which is len(NAME) + 2
        prop_prefix_len = len(key_upper) + 2
        # If prefix >= target column, use 1 space; otherwise pad to target column
        if prop_prefix_len >= target_column:
            padding = " "
        else:
            padding = " " * (target_column - prop_prefix_len)
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
            escaped_body = escape_org_content(issue.body.strip())
            lines.append(escaped_body)

        # Comments as sub-headings
        if issue.comments:
            comment_stars = "*" * (level + 1)

            for comment in sorted(issue.comments, key=lambda c: c.created_at):
                timestamp = format_timestamp(comment.created_at)
                lines.append(f"{comment_stars} Comment by @{comment.author.login} {timestamp}")

                if comment.body:
                    escaped_comment = escape_org_content(comment.body.strip())
                    lines.append(escaped_comment)

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

        # If raw_text is available, use it directly (preserves original formatting)
        if heading.raw_text is not None:
            lines.append(heading.raw_text)
        else:
            # Otherwise, generate from scratch
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

        # Children (always appended regardless of raw_text)
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
