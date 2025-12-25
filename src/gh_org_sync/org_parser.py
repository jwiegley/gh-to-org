"""
Org-mode file parser.

This module provides regex-based parsing of Org-mode files,
extracting headings, properties, tags, and content into structured data.
"""

import logging
import re
from pathlib import Path

from .exceptions import OrgParseError
from .models import OrgHeading, OrgTodoState

logger = logging.getLogger(__name__)

# Regex patterns for Org-mode elements
HEADING_PATTERN = re.compile(
    r"^(\*+)"  # Heading level (capture group 1)
    r"\s+"  # Required whitespace
    r"(?:(TODO|DONE)\s+)?"  # Optional TODO state (capture group 2)
    r"(.+?)"  # Title (capture group 3, non-greedy)
    r"(?:\s+(:[a-zA-Z0-9_@#%:]+:))?"  # Optional tags (capture group 4)
    r"\s*$"  # Trailing whitespace
)

PROPERTY_DRAWER_START = re.compile(r"^\s*:PROPERTIES:\s*$", re.IGNORECASE)
PROPERTY_DRAWER_END = re.compile(r"^\s*:END:\s*$", re.IGNORECASE)
PROPERTY_LINE = re.compile(
    r"^\s*:([A-Za-z0-9_-]+):\s*(.*?)\s*$"  # :NAME: value
)

# File header patterns
FILE_DIRECTIVE = re.compile(r"^#\+([A-Za-z_]+):\s*(.*)$")


class OrgParser:
    """
    Parser for Org-mode files.

    Parses Org files into a tree structure of OrgHeading objects,
    preserving properties, tags, and content.
    """

    def __init__(self) -> None:
        """Initialize the parser."""
        self._current_line = 0
        self._file_path: str = ""

    def parse_file(self, path: Path | str) -> list[OrgHeading]:
        """
        Parse an Org-mode file into a list of headings.

        Args:
            path: Path to the Org file

        Returns:
            List of top-level OrgHeading objects with children nested

        Raises:
            OrgParseError: If file cannot be read or parsed
        """
        path = Path(path)
        self._file_path = str(path)

        if not path.exists():
            logger.debug(f"File does not exist: {path}")
            return []

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            raise OrgParseError(str(path), details=str(e)) from e

        return self.parse_string(content)

    def parse_string(self, content: str) -> list[OrgHeading]:
        """
        Parse Org-mode content from a string.

        Args:
            content: Org-mode formatted string

        Returns:
            List of top-level OrgHeading objects
        """
        lines = content.split("\n")
        self._current_line = 0

        # Parse into flat list first
        flat_headings: list[OrgHeading] = []
        preamble_lines: list[str] = []  # Lines before first heading
        in_preamble = True

        i = 0
        while i < len(lines):
            self._current_line = i + 1
            line = lines[i]

            # Check for heading
            heading_match = HEADING_PATTERN.match(line)
            if heading_match:
                in_preamble = False
                heading, consumed = self._parse_heading(lines, i)
                flat_headings.append(heading)
                i += consumed
            else:
                if in_preamble:
                    preamble_lines.append(line)
                i += 1

        # Build tree structure from flat list
        return self._build_tree(flat_headings)

    def _parse_heading(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[OrgHeading, int]:
        """
        Parse a heading and its content.

        Args:
            lines: All lines in the file
            start_index: Index of the heading line

        Returns:
            Tuple of (OrgHeading, number of lines consumed)
        """
        line = lines[start_index]
        match = HEADING_PATTERN.match(line)

        if not match:
            raise OrgParseError(
                self._file_path,
                line=start_index + 1,
                details=f"Expected heading but found: {line[:50]}...",
            )

        stars, todo_state, title, tags_str = match.groups()

        # Parse level
        level = len(stars)

        # Parse TODO state
        state = None
        if todo_state:
            try:
                state = OrgTodoState(todo_state)
            except ValueError:
                state = None

        # Parse tags
        tags: list[str] = []
        if tags_str:
            # Remove surrounding colons and split
            tags = [t for t in tags_str.strip(":").split(":") if t]

        # Initialize heading
        heading = OrgHeading(
            level=level,
            title=title.strip(),
            todo_state=state,
            tags=tags,
            properties={},
            content="",
            children=[],
            source_line=start_index + 1,
        )

        # Parse content following the heading
        content_lines: list[str] = []
        i = start_index + 1
        consumed = 1

        # First, check for properties drawer
        if i < len(lines) and PROPERTY_DRAWER_START.match(lines[i]):
            props, prop_lines = self._parse_properties_drawer(lines, i)
            heading.properties = props
            i += prop_lines
            consumed += prop_lines

        # Then collect content until next heading of same or higher level
        while i < len(lines):
            line = lines[i]

            # Check if this is a heading
            heading_match = HEADING_PATTERN.match(line)
            if heading_match:
                next_level = len(heading_match.group(1))
                # Stop if same level or higher (parent/sibling)
                if next_level <= level:
                    break
                # Otherwise it's a child - stop here, will be parsed separately
                break

            content_lines.append(line)
            i += 1
            consumed += 1

        # Join content, stripping trailing empty lines
        heading.content = "\n".join(content_lines).rstrip()

        # Store raw text (from heading line to end of entry, excluding children)
        end_index = start_index + consumed
        raw_lines = lines[start_index:end_index]
        heading.raw_text = "\n".join(raw_lines)

        return heading, consumed

    def _parse_properties_drawer(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[dict[str, str], int]:
        """
        Parse a :PROPERTIES: drawer.

        Args:
            lines: All lines in the file
            start_index: Index of :PROPERTIES: line

        Returns:
            Tuple of (properties dict, number of lines consumed)
        """
        properties: dict[str, str] = {}
        i = start_index + 1  # Skip :PROPERTIES: line
        consumed = 1

        while i < len(lines):
            line = lines[i]
            consumed += 1

            # Check for :END:
            if PROPERTY_DRAWER_END.match(line):
                break

            # Parse property
            prop_match = PROPERTY_LINE.match(line)
            if prop_match:
                name, value = prop_match.groups()
                properties[name.upper()] = value

            i += 1

        return properties, consumed

    def _build_tree(self, flat_headings: list[OrgHeading]) -> list[OrgHeading]:
        """
        Build a tree structure from a flat list of headings.

        Uses heading levels to determine parent-child relationships.

        Args:
            flat_headings: List of headings in document order

        Returns:
            List of top-level headings with children nested
        """
        if not flat_headings:
            return []

        result: list[OrgHeading] = []
        stack: list[OrgHeading] = []

        for heading in flat_headings:
            # Pop from stack until we find a potential parent
            while stack and stack[-1].level >= heading.level:
                stack.pop()

            if not stack:
                # Top-level heading
                result.append(heading)
            else:
                # Child of the heading at top of stack
                stack[-1].children.append(heading)

            stack.append(heading)

        return result

    def extract_file_metadata(self, path: Path | str) -> dict[str, str]:
        """
        Extract file-level metadata (#+TITLE:, etc).

        Args:
            path: Path to Org file

        Returns:
            Dictionary of directive name -> value
        """
        path = Path(path)
        if not path.exists():
            return {}

        metadata: dict[str, str] = {}

        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    # Stop at first heading
                    if line.startswith("*"):
                        break

                    match = FILE_DIRECTIVE.match(line)
                    if match:
                        name, value = match.groups()
                        metadata[name.upper()] = value.strip()
        except OSError:
            pass

        return metadata


def find_heading_by_property(
    headings: list[OrgHeading],
    property_name: str,
    property_value: str,
) -> OrgHeading | None:
    """
    Find a heading with a specific property value.

    Searches recursively through all headings and children.

    Args:
        headings: List of headings to search
        property_name: Property name (case-insensitive)
        property_value: Expected property value

    Returns:
        Matching OrgHeading or None
    """
    prop_upper = property_name.upper()

    for heading in headings:
        if heading.properties.get(prop_upper) == property_value:
            return heading

        # Search children
        child_result = find_heading_by_property(
            heading.children,
            property_name,
            property_value,
        )
        if child_result:
            return child_result

    return None


def find_heading_by_github_number(
    headings: list[OrgHeading],
    number: int,
) -> OrgHeading | None:
    """
    Find a heading for a specific GitHub issue number.

    Args:
        headings: List of headings to search
        number: GitHub issue number

    Returns:
        Matching OrgHeading or None
    """
    return find_heading_by_property(headings, "GITHUB_NUMBER", str(number))


def collect_all_headings(headings: list[OrgHeading]) -> list[OrgHeading]:
    """
    Flatten a tree of headings into a list.

    Args:
        headings: List of potentially nested headings

    Returns:
        Flat list of all headings
    """
    result: list[OrgHeading] = []

    for heading in headings:
        result.append(heading)
        result.extend(collect_all_headings(heading.children))

    return result
