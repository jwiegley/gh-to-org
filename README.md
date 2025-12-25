# GitHub Issues to Org-mode Sync Tool

Convert GitHub issues to Org-mode format for seamless integration with Emacs workflows.

## Overview

This tool provides a robust Python module for formatting GitHub issues as proper Org-mode TODO entries, complete with:

- **TODO/DONE states** based on issue status
- **Properties drawers** with metadata (URL, ID, dates, labels, etc.)
- **Tags** from GitHub labels
- **Hierarchical comments** as sub-headings
- **Proper escaping** of Org-mode special characters
- **Timestamp formatting** compatible with Org-mode

## Files

- `org_formatter.py` - Main formatter module with `OrgFormatter` class
- `test_org_formatter.py` - Comprehensive test suite (32 tests)
- `ORG_MODE_FORMAT_GUIDE.md` - Detailed guide on Org-mode syntax
- `example_output.org` - Sample output showing formatted issues

## Quick Start

### Basic Usage

```python
from datetime import datetime
from org_formatter import OrgFormatter, format_org_file_header

# Create formatter
formatter = OrgFormatter()

# Format an issue
issue = {
    'title': 'Fix authentication bug',
    'number': 123,
    'state': 'open',
    'url': 'https://github.com/user/repo/issues/123',
    'created_at': datetime(2024, 1, 15, 10, 30),
    'labels': ['bug', 'urgent'],
    'body': 'Users cannot log in.',
    'author': 'johndoe',
    'comments': [
        {
            'author': 'developer',
            'created_at': datetime(2024, 1, 15, 14, 0),
            'body': 'Investigating the issue.'
        }
    ]
}

# Generate Org-mode output
org_content = format_org_file_header("GitHub Issues", "Repository: user/repo")
org_content += formatter.format_issue_from_dict(issue)

# Write to file
with open('issues.org', 'w') as f:
    f.write(org_content)
```

### Output Example

```org
#+TITLE: GitHub Issues
#+DESCRIPTION: Repository: user/repo
#+STARTUP: overview

* TODO Fix authentication bug :LINK:bug:urgent:
  :PROPERTIES:
  :URL:       https://github.com/user/repo/issues/123
  :ID:        123
  :STATE:     open
  :CREATED:   [2024-01-15 Mon 10:30]
  :AUTHOR:    johndoe
  :LABELS:    bug, urgent
  :COMMENTS:  1
  :END:

Users cannot log in.

** Comment by @developer [2024-01-15 Mon 14:00]
Investigating the issue.
```

## Key Features

### 1. Automatic Escaping

The formatter automatically escapes Org-mode special characters:

```python
# Lines starting with * are escaped
body = "* This would be a heading"
# Becomes: ", * This would be a heading"

# Lines starting with # are escaped
body = "# This would be a comment"
# Becomes: ", # This would be a comment"

# Org-mode link brackets are escaped
body = "See [[link][description]]"
# Becomes: "See \[\[link\]\[description\]\]"
```

### 2. Proper Timestamp Formatting

Timestamps follow Org-mode conventions:

```python
from datetime import datetime

dt = datetime(2024, 1, 15, 10, 30)

# Inactive timestamp (documentation only)
formatter.format_timestamp(dt)
# => '[2024-01-15 Mon 10:30]'

# Active timestamp (appears in Org agenda)
formatter.format_timestamp(dt, active=True)
# => '<2024-01-15 Mon 10:30>'
```

### 3. Tag Management

Tags are automatically cleaned and formatted:

```python
# Handles spaces, colons, and special characters
tags = ['priority: high', 'needs review', 'bug']
formatter.format_tags(tags)
# => ':LINK:priority_high:needs_review:bug:'
```

### 4. Properties Drawer

Rich metadata stored in properties drawer:

```python
properties = {
    'URL': 'https://github.com/user/repo/issues/123',
    'ID': 123,
    'STATE': 'open',
    'CREATED': datetime(2024, 1, 15, 10, 30),
    'LABELS': 'bug, urgent',
}
formatter.format_properties(properties)
```

Output:
```org
  :PROPERTIES:
  :URL:     https://github.com/user/repo/issues/123
  :ID:      123
  :STATE:   open
  :CREATED: [2024-01-15 Mon 10:30]
  :LABELS:  bug, urgent
  :END:
```

### 5. Hierarchical Comments

Comments are formatted as sub-headings for easy folding:

```org
* TODO Main issue :LINK:
** Comment by @user1 [2024-01-15 Mon 10:00]
First comment
** Comment by @user2 [2024-01-15 Mon 11:00]
Reply comment
```

## API Reference

### `OrgFormatter` Class

Main formatter class for converting GitHub data to Org-mode.

#### Constructor

```python
formatter = OrgFormatter(add_link_tag=True)
```

- `add_link_tag`: If True, adds `:LINK:` tag to all issue headings

#### Methods

##### `format_timestamp(dt, active=False)`

Format datetime as Org-mode timestamp.

```python
OrgFormatter.format_timestamp(datetime(2024, 1, 15, 10, 30))
# => '[2024-01-15 Mon 10:30]'
```

##### `escape_content(text)`

Escape text for safe inclusion in Org-mode.

```python
OrgFormatter.escape_content("* This looks like a heading")
# => ', * This looks like a heading'
```

##### `format_tags(tags, include_link=True)`

Format tags for Org-mode heading.

```python
OrgFormatter.format_tags(['bug', 'urgent'])
# => ':LINK:bug:urgent:'
```

##### `format_properties(properties, indent="  ")`

Format properties as PROPERTIES drawer.

```python
OrgFormatter.format_properties({'URL': 'https://example.com', 'ID': 123})
```

##### `format_issue(...)`

Format complete GitHub issue as Org-mode entry.

```python
formatter.format_issue(
    title='Issue title',
    number=123,
    state='open',
    url='https://github.com/user/repo/issues/123',
    created_at=datetime.now(),
    labels=['bug'],
    body='Issue description',
    comments=[...],
    level=1  # Heading level (* vs ** vs ***)
)
```

##### `format_issue_from_dict(issue, level=1)`

Convenience method to format issue from dictionary.

```python
issue = {
    'title': 'Issue title',
    'number': 123,
    'state': 'open',
    'url': 'https://github.com/user/repo/issues/123',
    'labels': ['bug'],
    'body': 'Description',
    'comments': []
}
formatter.format_issue_from_dict(issue)
```

### Helper Functions

##### `format_org_file_header(title, description="", author="", startup_options=None)`

Format Org-mode file header with metadata.

```python
format_org_file_header(
    "GitHub Issues",
    "Synced from user/repo",
    "Bot",
    ['overview', 'hidestars']
)
```

## Testing

Run the comprehensive test suite:

```bash
python test_org_formatter.py
```

The test suite includes:
- 32 test cases
- Unit tests for all formatting functions
- Complex scenario tests (code blocks, links, properties)
- Edge case tests (empty values, Unicode, long content)

## Org-mode Syntax Reference

### Issue Structure

```org
* TODO Issue Title :LINK:tag1:tag2:
  :PROPERTIES:
  :PROPERTY_NAME: value
  :END:

Issue body text here.

** Comment by @username [2024-01-15 Mon 10:00]
Comment text here.
```

### TODO States

- `TODO` - Open issue
- `DONE` - Closed issue
- Custom states: `IN-PROGRESS`, `WAITING`, etc.

### Timestamps

- Inactive: `[2024-01-15 Mon 10:30]` - Documentation only
- Active: `<2024-01-15 Mon 10:30>` - Appears in Org agenda

### Special Characters to Escape

- Lines starting with `*` (heading marker)
- Lines starting with `#` (comment)
- Lines starting with `#+` (directives)
- Lines starting with `:WORD:` (property/drawer)
- Double brackets `[[` and `]]` (link syntax)

## Integration Examples

### With GitHub API

```python
from github import Github
from org_formatter import OrgFormatter, format_org_file_header

g = Github("your_token")
repo = g.get_repo("user/repo")
formatter = OrgFormatter()

output = format_org_file_header(f"{repo.name} Issues", f"Repository: {repo.full_name}")

for issue in repo.get_issues(state='all'):
    issue_data = {
        'title': issue.title,
        'number': issue.number,
        'state': issue.state,
        'url': issue.html_url,
        'created_at': issue.created_at,
        'updated_at': issue.updated_at,
        'closed_at': issue.closed_at,
        'author': issue.user.login,
        'assignee': issue.assignee.login if issue.assignee else '',
        'labels': [label.name for label in issue.labels],
        'milestone': issue.milestone.title if issue.milestone else '',
        'body': issue.body or '',
        'comments': [
            {
                'author': comment.user.login,
                'created_at': comment.created_at,
                'body': comment.body
            }
            for comment in issue.get_comments()
        ]
    }
    output += '\n' + formatter.format_issue_from_dict(issue_data)

with open('github-issues.org', 'w') as f:
    f.write(output)
```

### With GraphQL API

```python
import requests
from datetime import datetime
from org_formatter import OrgFormatter, format_org_file_header

# GraphQL query to fetch issues
query = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, states: [OPEN, CLOSED]) {
      nodes {
        number
        title
        state
        url
        createdAt
        updatedAt
        closedAt
        author { login }
        assignees(first: 1) { nodes { login } }
        labels(first: 10) { nodes { name } }
        milestone { title }
        body
        comments(first: 50) {
          nodes {
            author { login }
            createdAt
            body
          }
        }
      }
    }
  }
}
"""

headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    'https://api.github.com/graphql',
    json={'query': query, 'variables': {'owner': 'user', 'name': 'repo'}},
    headers=headers
)

formatter = OrgFormatter()
output = format_org_file_header("GitHub Issues", "Synced via GraphQL")

for issue in response.json()['data']['repository']['issues']['nodes']:
    issue_data = {
        'title': issue['title'],
        'number': issue['number'],
        'state': issue['state'].lower(),
        'url': issue['url'],
        'created_at': datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00')),
        'updated_at': datetime.fromisoformat(issue['updatedAt'].replace('Z', '+00:00')),
        'closed_at': datetime.fromisoformat(issue['closedAt'].replace('Z', '+00:00')) if issue['closedAt'] else None,
        'author': issue['author']['login'],
        'assignee': issue['assignees']['nodes'][0]['login'] if issue['assignees']['nodes'] else '',
        'labels': [label['name'] for label in issue['labels']['nodes']],
        'milestone': issue['milestone']['title'] if issue['milestone'] else '',
        'body': issue['body'] or '',
        'comments': [
            {
                'author': comment['author']['login'],
                'created_at': datetime.fromisoformat(comment['createdAt'].replace('Z', '+00:00')),
                'body': comment['body']
            }
            for comment in issue['comments']['nodes']
        ]
    }
    output += '\n' + formatter.format_issue_from_dict(issue_data)

with open('github-issues.org', 'w') as f:
    f.write(output)
```

## Emacs Integration

Open the generated `.org` file in Emacs:

```bash
emacs github-issues.org
```

### Useful Emacs Commands

- `TAB` - Fold/unfold heading
- `S-TAB` - Cycle global visibility
- `C-c C-x p` - Set/view property
- `C-c C-t` - Cycle TODO state
- `C-c C-o` - Open link (URL property)
- `C-c a t` - Show TODO items in agenda
- `C-c \` - Search by tag

### Org-mode Configuration

Add to your Emacs init file for better experience:

```elisp
;; Custom TODO states
(setq org-todo-keywords
      '((sequence "TODO" "IN-PROGRESS" "|" "DONE" "CANCELLED")))

;; Tag colors
(setq org-tag-alist
      '(("LINK" . (:foreground "blue"))
        ("bug" . (:foreground "red"))
        ("enhancement" . (:foreground "green"))
        ("urgent" . (:foreground "orange"))))

;; Automatically show all issue headings
(setq org-startup-folded 'content)

;; Enable org-habit for tracking
(add-to-list 'org-modules 'org-habit)
```

## Best Practices

1. **Use inactive timestamps** `[...]` for metadata (created, updated dates)
2. **Use active timestamps** `<...>` only if you want items in Org agenda
3. **Keep tags consistent** - normalize labels before passing to formatter
4. **Add LINK tag** to distinguish external issues from local TODOs
5. **Use hierarchical structure** - comments as sub-headings for foldability
6. **Regular sync** - Update the .org file periodically to stay in sync

## Troubleshooting

### Issue: Content not parsing correctly in Emacs

**Solution**: Check that special characters are properly escaped. Run test suite to verify:

```bash
python test_org_formatter.py
```

### Issue: Tags not displaying

**Solution**: Ensure tags have no spaces and are properly formatted with colons:

```python
# Wrong
":tag with spaces:"

# Correct
":tag_with_underscores:"
```

### Issue: Properties drawer not recognized

**Solution**: Verify the drawer format:

```org
* TODO Title
  :PROPERTIES:    ← Must be exactly this, with colons
  :KEY: value     ← Property format
  :END:           ← Must be exactly this
```

### Issue: Timestamps not clickable in Emacs

**Solution**: Check timestamp format matches exactly:

```org
[2024-01-15 Mon 10:30]  ← Correct
[2024-1-15 Mon 10:30]   ← Wrong (missing leading zero)
[2024-01-15]            ← Partially correct (missing time)
```

## Contributing

To add features or fix bugs:

1. Add test cases to `test_org_formatter.py`
2. Implement changes in `org_formatter.py`
3. Run test suite to verify: `python test_org_formatter.py`
4. Update documentation

## License

This tool is provided as-is for syncing GitHub issues to Org-mode format.

## Resources

- [Org-mode Manual](https://orgmode.org/manual/)
- [GitHub API Documentation](https://docs.github.com/en/rest)
- [PyGithub Library](https://pygithub.readthedocs.io/)
- Detailed syntax guide: See `ORG_MODE_FORMAT_GUIDE.md`
