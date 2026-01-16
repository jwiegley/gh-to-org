#!/usr/bin/env python3
"""
Tests for org_formatter module.

Run with: python test_org_formatter.py
"""

import unittest
from datetime import datetime
from org_formatter import OrgFormatter, format_org_file_header


class TestOrgFormatter(unittest.TestCase):
    """Test cases for OrgFormatter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = OrgFormatter()

    def test_format_timestamp_inactive(self):
        """Test inactive timestamp formatting."""
        dt = datetime(2024, 1, 15, 10, 30)
        result = OrgFormatter.format_timestamp(dt, active=False)
        self.assertEqual(result, '[2024-01-15 Mon 10:30]')

    def test_format_timestamp_active(self):
        """Test active timestamp formatting."""
        dt = datetime(2024, 1, 15, 10, 30)
        result = OrgFormatter.format_timestamp(dt, active=True)
        self.assertEqual(result, '<2024-01-15 Mon 10:30>')

    def test_escape_content_asterisk(self):
        """Test escaping lines starting with asterisk."""
        text = "* This looks like a heading"
        result = OrgFormatter.escape_content(text)
        self.assertEqual(result, ', * This looks like a heading')

    def test_escape_content_hash(self):
        """Test escaping lines starting with hash."""
        text = "# This looks like a comment"
        result = OrgFormatter.escape_content(text)
        self.assertEqual(result, ', # This looks like a comment')

    def test_escape_content_directive(self):
        """Test escaping lines starting with #+."""
        text = "#+BEGIN_SRC python"
        result = OrgFormatter.escape_content(text)
        self.assertEqual(result, ', #+BEGIN_SRC python')

    def test_escape_content_property(self):
        """Test escaping lines that look like properties."""
        text = ":PROPERTIES: should be escaped"
        result = OrgFormatter.escape_content(text)
        self.assertEqual(result, ', :PROPERTIES: should be escaped')

    def test_escape_content_brackets(self):
        """Test escaping Org-mode link brackets."""
        text = "This has [[literal brackets]] in it"
        result = OrgFormatter.escape_content(text)
        self.assertEqual(result, r'This has \[\[literal brackets\]\] in it')

    def test_escape_content_multiline(self):
        """Test escaping multiline content."""
        text = """Normal line
* Looks like heading
# Looks like comment
Another normal line"""
        result = OrgFormatter.escape_content(text)
        expected = """Normal line
, * Looks like heading
, # Looks like comment
Another normal line"""
        self.assertEqual(result, expected)

    def test_escape_content_with_indent(self):
        """Test escaping preserves indentation."""
        text = "  * Indented asterisk"
        result = OrgFormatter.escape_content(text)
        self.assertEqual(result, '  , * Indented asterisk')

    def test_escape_content_normal_text(self):
        """Test that normal text is not modified."""
        text = "This is normal text with no special chars"
        result = OrgFormatter.escape_content(text)
        self.assertEqual(result, text)

    def test_format_tags_basic(self):
        """Test basic tag formatting."""
        tags = ['bug', 'urgent']
        result = OrgFormatter.format_tags(tags)
        self.assertEqual(result, ':LINK:bug:urgent:')

    def test_format_tags_no_link(self):
        """Test tag formatting without LINK tag."""
        tags = ['bug', 'urgent']
        result = OrgFormatter.format_tags(tags, include_link=False)
        self.assertEqual(result, ':bug:urgent:')

    def test_format_tags_with_spaces(self):
        """Test tag formatting with spaces in tags."""
        tags = ['priority: high', 'needs review']
        result = OrgFormatter.format_tags(tags, include_link=False)
        self.assertEqual(result, ':priority_high:needs_review:')

    def test_format_tags_empty(self):
        """Test tag formatting with empty list."""
        result = OrgFormatter.format_tags([], include_link=False)
        self.assertEqual(result, '')

    def test_format_properties_basic(self):
        """Test basic properties formatting with target column alignment."""
        props = {'URL': 'https://example.com', 'ID': 123}
        result = OrgFormatter.format_properties(props)
        # Target column is 11, so :ID: (4 chars) gets 7 spaces, :URL: (5 chars) gets 6 spaces
        # Properties are output in dictionary order (insertion order in Python 3.7+)
        expected = """  :PROPERTIES:
  :URL:      https://example.com
  :ID:       123
  :END:"""
        self.assertEqual(result, expected)

    def test_format_properties_with_datetime(self):
        """Test properties with datetime values."""
        dt = datetime(2024, 1, 15, 10, 30)
        props = {'CREATED': dt}
        result = OrgFormatter.format_properties(props)
        self.assertIn('[2024-01-15 Mon 10:30]', result)

    def test_format_properties_with_none(self):
        """Test properties with None values."""
        props = {'CLOSED': None}
        result = OrgFormatter.format_properties(props)
        expected = """  :PROPERTIES:
  :CLOSED:
  :END:"""
        self.assertEqual(result, expected)

    def test_format_issue_basic(self):
        """Test basic issue formatting."""
        result = self.formatter.format_issue(
            title='Test Issue',
            number=123,
            state='open',
            url='https://github.com/user/repo/issues/123',
            labels=['bug'],
        )

        # Check key components are present
        self.assertIn('* TODO Test Issue', result)
        self.assertIn(':LINK:bug:', result)
        self.assertIn(':PROPERTIES:', result)
        # Alignment uses target column 11: :URL: (5) + 6 spaces, :ID: (4) + 7 spaces, :STATE: (7) + 4 spaces
        self.assertIn(':URL:      https://github.com/user/repo/issues/123', result)
        self.assertIn(':ID:       123', result)
        self.assertIn(':STATE:    open', result)

    def test_format_issue_closed(self):
        """Test closed issue formatting."""
        closed_at = datetime(2024, 1, 15, 18, 30)
        result = self.formatter.format_issue(
            title='Closed Issue',
            number=124,
            state='closed',
            url='https://github.com/user/repo/issues/124',
            closed_at=closed_at,
            labels=['enhancement'],
        )

        # Check TODO state is DONE
        self.assertIn('* DONE Closed Issue', result)
        # Check CLOSED timestamp is present
        self.assertIn('CLOSED: [2024-01-15 Mon 18:30]', result)

    def test_format_issue_with_body(self):
        """Test issue formatting with body text."""
        body = """This is the issue description.

It has multiple paragraphs.

* It even has special characters"""

        result = self.formatter.format_issue(
            title='Issue with Body',
            number=125,
            state='open',
            url='https://github.com/user/repo/issues/125',
            body=body,
        )

        # Body should be escaped
        self.assertIn('This is the issue description.', result)
        self.assertIn(', * It even has special characters', result)

    def test_format_issue_with_comments(self):
        """Test issue formatting with comments."""
        comments = [
            {
                'author': 'user1',
                'created_at': datetime(2024, 1, 15, 10, 0),
                'body': 'First comment'
            },
            {
                'author': 'user2',
                'created_at': datetime(2024, 1, 15, 11, 0),
                'body': 'Second comment'
            }
        ]

        result = self.formatter.format_issue(
            title='Issue with Comments',
            number=126,
            state='open',
            url='https://github.com/user/repo/issues/126',
            comments=comments,
        )

        # Check comments are formatted as sub-headings
        self.assertIn('** Comment by @user1 [2024-01-15 Mon 10:00]', result)
        self.assertIn('First comment', result)
        self.assertIn('** Comment by @user2 [2024-01-15 Mon 11:00]', result)
        self.assertIn('Second comment', result)
        # :COMMENTS: (10 chars) >= 11, so just 1 space padding
        self.assertIn(':COMMENTS: 2', result)

    def test_format_issue_hierarchical_level(self):
        """Test issue formatting with different heading levels."""
        result = self.formatter.format_issue(
            title='Nested Issue',
            number=127,
            state='open',
            url='https://github.com/user/repo/issues/127',
            level=2
        )

        # Should be level 2 heading
        self.assertIn('** TODO Nested Issue', result)

    def test_format_issue_from_dict(self):
        """Test formatting issue from dictionary."""
        issue = {
            'title': 'Dict Issue',
            'number': 128,
            'state': 'open',
            'url': 'https://github.com/user/repo/issues/128',
            'labels': ['bug', 'urgent'],
            'body': 'Issue body',
        }

        result = self.formatter.format_issue_from_dict(issue)

        self.assertIn('* TODO Dict Issue', result)
        self.assertIn(':LINK:bug:urgent:', result)
        self.assertIn('Issue body', result)

    def test_format_org_file_header(self):
        """Test file header formatting."""
        result = format_org_file_header(
            title='Test Issues',
            description='Test description',
            author='Test Author',
            startup_options=['overview', 'hidestars']
        )

        self.assertIn('#+TITLE: Test Issues', result)
        self.assertIn('#+DESCRIPTION: Test description', result)
        self.assertIn('#+AUTHOR: Test Author', result)
        self.assertIn('#+STARTUP: overview hidestars', result)


class TestComplexScenarios(unittest.TestCase):
    """Test complex real-world scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = OrgFormatter()

    def test_issue_with_code_blocks(self):
        """Test issue containing code blocks."""
        body = """Here's the problematic code:

```python
def authenticate(user):
    * Get token
    # Check validity
    return token
```

The asterisk and hash cause issues."""

        result = self.formatter.format_issue(
            title='Code Block Issue',
            number=200,
            state='open',
            url='https://github.com/user/repo/issues/200',
            body=body,
        )

        # Code block markers should be preserved
        self.assertIn('```python', result)
        # But asterisk in code should be escaped
        self.assertIn(', * Get token', result)
        self.assertIn(', # Check validity', result)

    def test_issue_with_org_links(self):
        """Test issue containing Org-mode link syntax."""
        body = "See [[https://example.com][this link]] for details."

        result = self.formatter.format_issue(
            title='Link Issue',
            number=201,
            state='open',
            url='https://github.com/user/repo/issues/201',
            body=body,
        )

        # Opening and closing bracket pairs should be escaped
        self.assertIn(r'\[\[', result)
        self.assertIn(r'\]\]', result)
        # The actual escaped content should be present
        self.assertIn('https://example.com', result)

    def test_issue_with_properties_like_text(self):
        """Test issue containing text that looks like properties."""
        body = """:PROPERTIES: drawer in the text
:KEY: value
:END:"""

        result = self.formatter.format_issue(
            title='Properties Issue',
            number=202,
            state='open',
            url='https://github.com/user/repo/issues/202',
            body=body,
        )

        # Property-like text should be escaped
        self.assertIn(', :PROPERTIES: drawer in the text', result)
        self.assertIn(', :KEY: value', result)
        self.assertIn(', :END:', result)

    def test_multiple_issues_in_file(self):
        """Test generating multiple issues for a file."""
        issues = [
            {
                'title': 'First Issue',
                'number': 1,
                'state': 'open',
                'url': 'https://github.com/user/repo/issues/1',
                'labels': ['bug'],
            },
            {
                'title': 'Second Issue',
                'number': 2,
                'state': 'closed',
                'url': 'https://github.com/user/repo/issues/2',
                'closed_at': datetime(2024, 1, 15, 10, 0),
                'labels': ['enhancement'],
            }
        ]

        output = format_org_file_header('Multiple Issues', 'Test Repository')
        for issue in issues:
            output += '\n' + self.formatter.format_issue_from_dict(issue)

        # Check both issues are present
        self.assertIn('* TODO First Issue', output)
        self.assertIn('* DONE Second Issue', output)
        self.assertIn('#+TITLE: Multiple Issues', output)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = OrgFormatter()

    def test_empty_title(self):
        """Test issue with empty title."""
        result = self.formatter.format_issue(
            title='',
            number=300,
            state='open',
            url='https://github.com/user/repo/issues/300',
        )

        # Should handle gracefully
        self.assertIn('* TODO ', result)

    def test_none_values(self):
        """Test issue with None values."""
        result = self.formatter.format_issue(
            title='None Values',
            number=301,
            state='open',
            url='https://github.com/user/repo/issues/301',
            created_at=None,
            updated_at=None,
            closed_at=None,
            author='',
            assignee='',
            labels=None,
            milestone='',
            body='',
            comments=None,
        )

        # Should handle gracefully without errors
        self.assertIn('* TODO None Values', result)
        self.assertIn(':PROPERTIES:', result)

    def test_very_long_title(self):
        """Test issue with very long title."""
        long_title = 'A' * 500
        result = self.formatter.format_issue(
            title=long_title,
            number=302,
            state='open',
            url='https://github.com/user/repo/issues/302',
        )

        # Should include full title
        self.assertIn(long_title, result)

    def test_unicode_content(self):
        """Test issue with Unicode characters."""
        result = self.formatter.format_issue(
            title='Unicode Test 测试 🚀',
            number=303,
            state='open',
            url='https://github.com/user/repo/issues/303',
            body='Content with emoji 😀 and Chinese 你好',
            author='用户',
        )

        # Unicode should be preserved
        self.assertIn('测试 🚀', result)
        self.assertIn('😀', result)
        self.assertIn('你好', result)
        self.assertIn('用户', result)


def run_tests():
    """Run all tests and display results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestOrgFormatter))
    suite.addTests(loader.loadTestsFromTestCase(TestComplexScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    import sys
    sys.exit(run_tests())
