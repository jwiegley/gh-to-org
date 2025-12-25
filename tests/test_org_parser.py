"""Tests for Org-mode parser."""

import tempfile
from pathlib import Path

import pytest

from gh_org_sync.models import OrgTodoState
from gh_org_sync.org_parser import (
    OrgParser,
    collect_all_headings,
    find_heading_by_github_number,
    find_heading_by_property,
)


class TestOrgParser:
    """Tests for OrgParser class."""

    def test_parse_empty_file(self) -> None:
        parser = OrgParser()
        headings = parser.parse_string("")
        assert headings == []

    def test_parse_simple_heading(self) -> None:
        parser = OrgParser()
        content = "* Test Heading"
        headings = parser.parse_string(content)

        assert len(headings) == 1
        assert headings[0].level == 1
        assert headings[0].title == "Test Heading"

    def test_parse_todo_heading(self) -> None:
        parser = OrgParser()
        content = "* TODO Task to do"
        headings = parser.parse_string(content)

        assert len(headings) == 1
        assert headings[0].todo_state == OrgTodoState.TODO
        assert headings[0].title == "Task to do"

    def test_parse_done_heading(self) -> None:
        parser = OrgParser()
        content = "* DONE Completed task"
        headings = parser.parse_string(content)

        assert len(headings) == 1
        assert headings[0].todo_state == OrgTodoState.DONE
        assert headings[0].title == "Completed task"

    def test_parse_heading_with_tags(self) -> None:
        parser = OrgParser()
        content = "* TODO Issue Title :LINK:bug:urgent:"
        headings = parser.parse_string(content)

        assert len(headings) == 1
        assert headings[0].tags == ["LINK", "bug", "urgent"]
        assert headings[0].title == "Issue Title"

    def test_parse_properties_drawer(self) -> None:
        parser = OrgParser()
        content = """* TODO Test
:PROPERTIES:
:URL: https://example.com
:ID: 123
:END:
"""
        headings = parser.parse_string(content)

        assert len(headings) == 1
        assert headings[0].properties["URL"] == "https://example.com"
        assert headings[0].properties["ID"] == "123"

    def test_parse_content(self) -> None:
        parser = OrgParser()
        content = """* TODO Test

This is the content.
With multiple lines.
"""
        headings = parser.parse_string(content)

        assert len(headings) == 1
        assert "This is the content" in headings[0].content
        assert "multiple lines" in headings[0].content

    def test_parse_nested_headings(self) -> None:
        parser = OrgParser()
        content = """* Parent
** Child 1
** Child 2
*** Grandchild
"""
        headings = parser.parse_string(content)

        assert len(headings) == 1  # Only top-level
        assert headings[0].title == "Parent"
        assert len(headings[0].children) == 2
        assert headings[0].children[0].title == "Child 1"
        assert headings[0].children[1].title == "Child 2"
        assert len(headings[0].children[1].children) == 1
        assert headings[0].children[1].children[0].title == "Grandchild"

    def test_parse_file(self, sample_org_content: str) -> None:
        parser = OrgParser()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".org", delete=False) as f:
            f.write(sample_org_content)
            temp_path = Path(f.name)

        try:
            headings = parser.parse_file(temp_path)

            assert len(headings) == 3
            assert headings[0].title == "First Issue"
            assert headings[0].todo_state == OrgTodoState.TODO
            assert headings[1].title == "Second Issue"
            assert headings[1].todo_state == OrgTodoState.DONE
            assert headings[2].title == "User Task"
        finally:
            temp_path.unlink()

    def test_parse_nonexistent_file(self) -> None:
        parser = OrgParser()
        headings = parser.parse_file(Path("/nonexistent/file.org"))
        assert headings == []


class TestHelperFunctions:
    """Tests for parser helper functions."""

    def test_find_heading_by_property(self, sample_org_content: str) -> None:
        parser = OrgParser()
        headings = parser.parse_string(sample_org_content)

        found = find_heading_by_property(headings, "GITHUB_NUMBER", "1")
        assert found is not None
        assert found.title == "First Issue"

        not_found = find_heading_by_property(headings, "GITHUB_NUMBER", "999")
        assert not_found is None

    def test_find_heading_by_github_number(self, sample_org_content: str) -> None:
        parser = OrgParser()
        headings = parser.parse_string(sample_org_content)

        found = find_heading_by_github_number(headings, 2)
        assert found is not None
        assert found.title == "Second Issue"

    def test_collect_all_headings(self) -> None:
        parser = OrgParser()
        content = """* Parent
** Child 1
** Child 2
* Another Parent
"""
        headings = parser.parse_string(content)
        all_headings = collect_all_headings(headings)

        assert len(all_headings) == 4
        titles = [h.title for h in all_headings]
        assert "Parent" in titles
        assert "Child 1" in titles
        assert "Child 2" in titles
        assert "Another Parent" in titles
