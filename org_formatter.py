#!/usr/bin/env python3
"""
Org-mode formatter for GitHub issues.

This module provides utilities to format GitHub issues and comments
into proper Org-mode syntax, handling all special characters, escaping,
and structural requirements.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
import re


class OrgFormatter:
    """Format GitHub data as Org-mode entries."""

    def __init__(self, add_link_tag: bool = True):
        """
        Initialize the formatter.

        Args:
            add_link_tag: If True, add :LINK: tag to all issue headings
        """
        self.add_link_tag = add_link_tag

    @staticmethod
    def format_timestamp(dt: datetime, active: bool = False) -> str:
        """
        Format datetime as Org-mode timestamp.

        Args:
            dt: datetime object
            active: If True, use <> for active timestamp (appears in agenda),
                   else [] for inactive timestamp (documentation only)

        Returns:
            Formatted timestamp string like [2024-01-15 Mon 10:30]

        Examples:
            >>> from datetime import datetime
            >>> dt = datetime(2024, 1, 15, 10, 30)
            >>> OrgFormatter.format_timestamp(dt)
            '[2024-01-15 Mon 10:30]'
            >>> OrgFormatter.format_timestamp(dt, active=True)
            '<2024-01-15 Mon 10:30>'
        """
        bracket = ('<', '>') if active else ('[', ']')
        return f"{bracket[0]}{dt.strftime('%Y-%m-%d %a %H:%M')}{bracket[1]}"

    @staticmethod
    def escape_content(text: str) -> str:
        """
        Escape text for safe inclusion in Org-mode content.

        Handles:
        - Lines starting with * (heading marker)
        - Lines starting with # (comment)
        - Lines starting with #+ (Org directives)
        - Lines starting with :WORD: (drawer/property syntax)
        - Literal [[ and ]] (Org-mode link syntax)

        Args:
            text: Raw text that may contain Org-mode special characters

        Returns:
            Escaped text safe for inclusion in Org-mode content

        Examples:
            >>> OrgFormatter.escape_content("* This looks like a heading")
            ', * This looks like a heading'
            >>> OrgFormatter.escape_content("Normal text")
            'Normal text'
        """
        if not text:
            return ""

        lines = text.split('\n')
        escaped_lines = []

        for line in lines:
            # Check if line starts with special characters
            # Preserve leading whitespace
            stripped = line.lstrip()
            if not stripped:
                escaped_lines.append(line)
                continue

            indent = line[:len(line) - len(stripped)]

            # Check for special line-start characters
            needs_escape = False

            if stripped.startswith('*'):
                needs_escape = True
            elif stripped.startswith('#'):
                needs_escape = True
            elif stripped.startswith('#+'):
                needs_escape = True
            elif stripped.startswith(':'):
                # Check if it looks like a property or drawer
                # Format: :WORD: or :WORD:WORD:
                if ':' in stripped[1:]:
                    colon_pos = stripped.index(':', 1)
                    potential_keyword = stripped[1:colon_pos]
                    # If it's alphanumeric/underscore, it's likely a property
                    if potential_keyword and re.match(r'^[A-Za-z_][A-Za-z0-9_-]*$', potential_keyword):
                        needs_escape = True

            if needs_escape:
                line = indent + ', ' + stripped

            # Escape Org-mode link brackets
            # Replace [[ with \[\[ and ]] with \]\]
            # Note: We need to escape both opening and closing pairs
            line = line.replace('[[', r'\[\[')
            line = line.replace(']]', r'\]\]')
            # Also handle cases where ] and [ appear separately within link syntax
            # Count brackets to ensure we're escaping correctly
            if r'\[\[' in line or r'\]\]' in line:
                # Already escaped, ensure middle content is preserved
                pass

            escaped_lines.append(line)

        return '\n'.join(escaped_lines)

    @staticmethod
    def format_tags(tags: List[str], include_link: bool = True) -> str:
        """
        Format tags for Org-mode heading.

        Tags are formatted as :tag1:tag2:tag3: at the end of a heading.
        Spaces and special characters in tags are replaced with underscores.

        Args:
            tags: List of tag strings
            include_link: If True, add :LINK: tag at the start

        Returns:
            Formatted tag string like :LINK:tag1:tag2:

        Examples:
            >>> OrgFormatter.format_tags(['bug', 'urgent'])
            ':LINK:bug:urgent:'
            >>> OrgFormatter.format_tags(['priority: high', 'needs review'], include_link=False)
            ':priority_high:needs_review:'
        """
        all_tags = []

        if include_link:
            all_tags.append('LINK')

        # Clean tags: replace spaces and special chars with underscores
        for tag in tags:
            if not tag:
                continue
            # Replace spaces, colons, and other problematic characters
            clean_tag = re.sub(r'[:\s]+', '_', tag.strip())
            # Remove leading/trailing underscores
            clean_tag = clean_tag.strip('_')
            if clean_tag:
                all_tags.append(clean_tag)

        if not all_tags:
            return ""

        return ':' + ':'.join(all_tags) + ':'

    @staticmethod
    def format_properties(properties: Dict[str, Any], indent: str = "  ") -> str:
        """
        Format properties as Org-mode PROPERTIES drawer.

        Args:
            properties: Dictionary of property name -> value
            indent: Indentation string (default: 2 spaces)

        Returns:
            Formatted properties drawer

        Examples:
            >>> props = {'URL': 'https://example.com', 'ID': 123}
            >>> print(OrgFormatter.format_properties(props))
              :PROPERTIES:
              :URL:       https://example.com
              :ID:        123
              :END:
        """
        if not properties:
            return ""

        lines = [f"{indent}:PROPERTIES:"]

        # Find longest property name for alignment
        max_len = max(len(str(k)) for k in properties.keys()) if properties else 0

        for key, value in properties.items():
            # Convert value to string, handle None
            if value is None:
                value_str = ""
            elif isinstance(value, datetime):
                value_str = OrgFormatter.format_timestamp(value)
            else:
                value_str = str(value)

            # Property names should be uppercase
            key_upper = str(key).upper()

            # Format with alignment
            # Only add padding space if there's a value
            if value_str:
                padding = ' ' * (max_len - len(key_upper) + 1)
                lines.append(f"{indent}:{key_upper}:{padding}{value_str}")
            else:
                lines.append(f"{indent}:{key_upper}:")

        lines.append(f"{indent}:END:")

        return '\n'.join(lines)

    def format_issue(
        self,
        title: str,
        number: int,
        state: str,
        url: str,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        closed_at: Optional[datetime] = None,
        author: str = "",
        assignee: str = "",
        labels: Optional[List[str]] = None,
        milestone: str = "",
        body: str = "",
        comments: Optional[List[Dict[str, Any]]] = None,
        level: int = 1
    ) -> str:
        """
        Format a GitHub issue as complete Org-mode entry.

        Args:
            title: Issue title
            number: Issue number
            state: Issue state ('open' or 'closed')
            url: Issue URL
            created_at: Creation timestamp
            updated_at: Last update timestamp
            closed_at: Closed timestamp (if closed)
            author: Issue author username
            assignee: Assignee username
            labels: List of label names
            milestone: Milestone name
            body: Issue body text
            comments: List of comment dictionaries with keys:
                     'author', 'created_at', 'body'
            level: Heading level (1 = *, 2 = **, etc.)

        Returns:
            Complete Org-mode formatted issue entry
        """
        labels = labels or []
        comments = comments or []

        # Determine TODO state
        todo_state = "DONE" if state == 'closed' else "TODO"

        # Format heading with tags
        stars = '*' * level
        tag_string = self.format_tags(labels, include_link=self.add_link_tag)
        heading = f"{stars} {todo_state} {title} {tag_string}\n"

        # Build properties drawer
        properties = {
            'URL': url,
            'ID': number,
            'STATE': state,
            'CREATED': created_at,
            'UPDATED': updated_at,
            'CLOSED': closed_at,
            'AUTHOR': author,
            'ASSIGNEE': assignee,
            'LABELS': ', '.join(labels),
            'MILESTONE': milestone,
            'COMMENTS': len(comments),
        }

        properties_text = self.format_properties(properties)

        # Add CLOSED timestamp for done items (Org-mode convention)
        closed_line = ""
        if state == 'closed' and closed_at:
            indent = "  "
            closed_line = f"{indent}CLOSED: {self.format_timestamp(closed_at)}\n"

        # Format body
        body_text = ""
        if body:
            escaped_body = self.escape_content(body)
            body_text = f"\n{escaped_body}\n"

        # Format comments as sub-headings
        comments_text = ""
        if comments:
            comment_level = level + 1
            comment_stars = '*' * comment_level
            for comment in comments:
                comment_author = comment.get('author', 'unknown')
                comment_created = comment.get('created_at')
                comment_body = comment.get('body', '')

                timestamp_str = ""
                if isinstance(comment_created, datetime):
                    timestamp_str = self.format_timestamp(comment_created)

                comments_text += f"\n{comment_stars} Comment by @{comment_author} {timestamp_str}\n"
                if comment_body:
                    escaped_comment = self.escape_content(comment_body)
                    comments_text += f"{escaped_comment}\n"

        return heading + properties_text + '\n' + closed_line + body_text + comments_text

    def format_issue_from_dict(self, issue: Dict[str, Any], level: int = 1) -> str:
        """
        Convenience method to format issue from dictionary.

        Args:
            issue: Dictionary containing issue data
            level: Heading level

        Returns:
            Formatted Org-mode entry

        Example:
            >>> formatter = OrgFormatter()
            >>> issue = {
            ...     'title': 'Bug report',
            ...     'number': 123,
            ...     'state': 'open',
            ...     'url': 'https://github.com/user/repo/issues/123',
            ...     'labels': ['bug'],
            ... }
            >>> print(formatter.format_issue_from_dict(issue))
        """
        return self.format_issue(
            title=issue.get('title', 'Untitled'),
            number=issue.get('number', 0),
            state=issue.get('state', 'open'),
            url=issue.get('url', ''),
            created_at=issue.get('created_at'),
            updated_at=issue.get('updated_at'),
            closed_at=issue.get('closed_at'),
            author=issue.get('author', ''),
            assignee=issue.get('assignee', ''),
            labels=issue.get('labels', []),
            milestone=issue.get('milestone', ''),
            body=issue.get('body', ''),
            comments=issue.get('comments', []),
            level=level
        )


def format_org_file_header(
    title: str,
    description: str = "",
    author: str = "",
    startup_options: Optional[List[str]] = None
) -> str:
    """
    Format Org-mode file header with metadata.

    Args:
        title: File title
        description: File description
        author: Author name
        startup_options: List of Org startup options (e.g., ['overview', 'hidestars'])

    Returns:
        Formatted file header

    Example:
        >>> print(format_org_file_header("GitHub Issues", "Synced from GitHub"))
        #+TITLE: GitHub Issues
        #+DESCRIPTION: Synced from GitHub
        #+STARTUP: overview
        <BLANKLINE>
    """
    startup_options = startup_options or ['overview']

    lines = []
    lines.append(f"#+TITLE: {title}")

    if description:
        lines.append(f"#+DESCRIPTION: {description}")

    if author:
        lines.append(f"#+AUTHOR: {author}")

    lines.append(f"#+STARTUP: {' '.join(startup_options)}")
    lines.append("")  # Blank line after header

    return '\n'.join(lines)


# Example usage and testing
if __name__ == "__main__":
    # Create formatter
    formatter = OrgFormatter()

    # Example issue
    example_issue = {
        'title': 'Fix authentication bug on mobile devices',
        'number': 123,
        'state': 'open',
        'url': 'https://github.com/myorg/myrepo/issues/123',
        'created_at': datetime(2024, 1, 15, 10, 30),
        'updated_at': datetime(2024, 1, 16, 14, 20),
        'closed_at': None,
        'author': 'johndoe',
        'assignee': 'janedeveloper',
        'labels': ['bug', 'mobile', 'authentication', 'priority: high'],
        'milestone': 'v2.0',
        'body': '''Users are reporting authentication failures on mobile app.

Steps to reproduce:
* Open mobile app
* Enter credentials
* Tap "Login"

Expected: User should be logged in successfully.''',
        'comments': [
            {
                'author': 'johndoe',
                'created_at': datetime(2024, 1, 15, 10, 30),
                'body': 'Initial report from user feedback.'
            },
            {
                'author': 'janedeveloper',
                'created_at': datetime(2024, 1, 15, 16, 45),
                'body': '''Investigating. Appears to be related to OAuth token refresh.

* Found issue in token_manager.py line 234

Code snippet shows the problem.'''
            }
        ]
    }

    # Generate file
    print(format_org_file_header(
        "GitHub Issues",
        "Synced from myorg/myrepo",
        "GitHub Issues Bot"
    ))

    print(formatter.format_issue_from_dict(example_issue))
    print()

    # Example closed issue
    closed_issue = {
        'title': 'Add dark mode support',
        'number': 124,
        'state': 'closed',
        'url': 'https://github.com/myorg/myrepo/issues/124',
        'created_at': datetime(2024, 1, 10, 9, 0),
        'updated_at': datetime(2024, 1, 14, 18, 30),
        'closed_at': datetime(2024, 1, 14, 18, 30),
        'author': 'designuser',
        'assignee': 'frontenddev',
        'labels': ['enhancement', 'ui'],
        'milestone': 'v2.0',
        'body': 'Add dark mode theme option to settings.',
        'comments': [
            {
                'author': 'frontenddev',
                'created_at': datetime(2024, 1, 10, 11, 0),
                'body': 'Working on this. Will use CSS custom properties.'
            },
            {
                'author': 'designuser',
                'created_at': datetime(2024, 1, 11, 10, 0),
                'body': '''Here are the color values:
# Background colors
* Background: #1a1a1a
* Text: #e0e0e0'''
            }
        ]
    }

    print(formatter.format_issue_from_dict(closed_issue))
