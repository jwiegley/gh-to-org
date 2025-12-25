# gh-org-sync

Sync GitHub and Gitea issues to Org-mode files with intelligent merging.

## Overview

`gh-org-sync` is a command-line tool that fetches issues from GitHub or Gitea repositories and formats them as proper Org-mode headings. It features smart merging that preserves your local additions while keeping GitHub data up-to-date.

**Key features:**

- **Smart merging** - Updates GitHub data while preserving user-added content
- **Multiple providers** - Works with both GitHub (via `gh` CLI) and Gitea
- **Rich metadata** - Properties drawer with timestamps, labels, assignees, milestones
- **Hierarchical comments** - Issue comments as foldable sub-headings
- **Markdown conversion** - Converts Markdown syntax to Org-mode equivalents
- **Safe operations** - Atomic writes with automatic backups

## Installation

### With Nix (recommended)

```bash
nix build
nix profile install .
```

### With pip/uv

```bash
pip install .
# or
uv pip install .
```

### Development install

```bash
uv pip install -e ".[dev]"
```

## Quick Start

### Prerequisites

For GitHub repositories, you need the [GitHub CLI](https://cli.github.com/) installed and authenticated:

```bash
gh auth login
```

For Gitea, you need an API token and the server URL.

### Basic Usage

```bash
# Sync all issues from a GitHub repo
gh-org-sync sync owner/repo

# Sync to a specific file
gh-org-sync sync owner/repo -o my-issues.org

# Sync only open issues
gh-org-sync sync owner/repo -s open

# Limit number of issues
gh-org-sync sync owner/repo --limit 50

# Dry run (show what would happen)
gh-org-sync sync owner/repo --dry-run
```

### Gitea Usage

```bash
# Set credentials via environment
export GITEA_URL=https://gitea.example.com
export GITEA_TOKEN=your_token

gh-org-sync sync owner/repo --provider gitea

# Or pass them directly
gh-org-sync sync owner/repo --provider gitea \
  --gitea-url https://gitea.example.com \
  --gitea-token your_token
```

## Commands

### `sync`

Sync issues from a repository to an Org-mode file.

```
gh-org-sync sync REPO [OPTIONS]
```

**Arguments:**
- `REPO` - Repository in `owner/repo` format

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output Org file path (default: `issues.org`) |
| `--state` | `-s` | Filter by state: `all`, `open`, `closed` (default: `all`) |
| `--limit` | `-l` | Maximum number of issues to fetch |
| `--no-comments` | | Don't include issue comments |
| `--dry-run` | `-n` | Show what would happen without writing |
| `--no-backup` | | Don't create backup of existing file |
| `--no-link-tag` | | Don't add `:LINK:` tag to headings |
| `--timeout` | | API timeout in seconds (default: 60) |
| `--provider` | `-p` | Issue provider: `github` or `gitea` |
| `--gitea-url` | | Gitea server URL |
| `--gitea-token` | | Gitea API token |
| `--verbose` | `-v` | Enable verbose output |
| `--log-level` | | Log level: `debug`, `info`, `warning`, `error` |

### `check`

Verify provider connection and authentication.

```bash
gh-org-sync check                     # Check GitHub CLI
gh-org-sync check --provider gitea    # Check Gitea connection
```

### `parse`

Parse an Org file and display its structure (useful for debugging).

```bash
gh-org-sync parse issues.org
```

## Output Format

Issues are formatted as Org-mode headings with full metadata:

```org
#+TITLE: GitHub Issues: owner/repo
#+DESCRIPTION: GitHub issues synced from owner/repo
#+STARTUP: overview
#+SYNC_REPO: owner/repo
#+SYNC_TIME: 2024-12-25T10:00:00+00:00

* TODO Fix authentication bug :LINK:bug:urgent:
:PROPERTIES:
:AUTHOR:         johndoe
:CREATED:        [2024-01-15 Mon 10:30]
:GITHUB_NUMBER:  123
:GITHUB_STATE:   open
:GITHUB_UPDATED: [2024-01-20 Sat 14:00]
:URL:            https://github.com/owner/repo/issues/123
:END:

Users cannot log in when using SSO.

** Comment by @developer [2024-01-15 Mon 14:00]
Investigating the issue.

** Comment by @developer [2024-01-16 Tue 09:30]
Found the root cause - fixing now.

* DONE Add dark mode support :LINK:enhancement:
:PROPERTIES:
:AUTHOR:         janedoe
:CLOSED:         [2024-01-18 Thu 16:00]
:CREATED:        [2024-01-10 Wed 08:00]
:GITHUB_NUMBER:  120
:GITHUB_STATE:   closed
:GITHUB_UPDATED: [2024-01-18 Thu 16:00]
:URL:            https://github.com/owner/repo/issues/120
:END:
CLOSED: [2024-01-18 Thu 16:00]

Implement dark mode toggle in settings.
```

## Intelligent Merging

`gh-org-sync` preserves your local modifications when re-syncing:

### What gets updated from GitHub:
- Issue title and body
- TODO state (open/closed)
- Labels (as tags)
- Properties (timestamps, assignees, milestones)
- Comments

### What gets preserved:
- User-added tags (not from GitHub labels)
- User-added properties (not `GITHUB_*` prefixed)
- User-added child headings (not comments)
- Headings without `GITHUB_NUMBER` property
- Content after the sync marker

### Matching Strategy

Issues are matched by the `GITHUB_NUMBER` property in the Org file. This means:

- **New issues** are appended at the end
- **Existing issues** are updated in place
- **Deleted issues** (in Org but not in GitHub) are preserved
- **User headings** (no `GITHUB_NUMBER`) are untouched

## Emacs Integration

Open the generated `.org` file in Emacs and use standard Org commands:

| Key | Command |
|-----|---------|
| `TAB` | Fold/unfold heading |
| `S-TAB` | Cycle global visibility |
| `C-c C-t` | Cycle TODO state |
| `C-c C-o` | Open URL at point |
| `C-c \` | Search by tag |
| `C-c a t` | Show TODOs in agenda |

### Recommended Configuration

```elisp
;; Custom TODO states
(setq org-todo-keywords
      '((sequence "TODO" "IN-PROGRESS" "|" "DONE" "CANCELLED")))

;; Show content on startup
(setq org-startup-folded 'content)

;; Open URLs with browse-url
(setq org-link-frame-setup '((file . find-file)))
```

## Markdown to Org Conversion

Issue bodies and comments are automatically converted from Markdown to Org-mode:

| Markdown | Org-mode |
|----------|----------|
| `[text](url)` | `[[url][text]]` |
| `**bold**` | `*bold*` |
| `*italic*` | `/italic/` |
| `` `code` `` | `=code=` |
| `~~strike~~` | `+strike+` |
| ` ```lang ` | `#+BEGIN_SRC lang` |
| `> quote` | `#+BEGIN_QUOTE` |

## API Usage

You can also use `gh-org-sync` as a Python library:

```python
from gh_org_sync.sync import run_sync

# Synchronous sync
result = run_sync(
    repo="owner/repo",
    output_file="issues.org",
    state_filter="open",
    limit=50,
)

print(f"Added: {result.added}")
print(f"Updated: {result.updated}")
print(f"Unchanged: {result.unchanged}")
```

### Async Usage

```python
import asyncio
from gh_org_sync.sync import IssueSync
from gh_org_sync.github_client import GitHubClient

async def main():
    client = GitHubClient()
    syncer = IssueSync(provider=client)

    result = await syncer.sync(
        repo="owner/repo",
        output_file="issues.org",
    )

    print(result.summary())
    await client.close()

asyncio.run(main())
```

## Development

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy src/
```

### Linting

```bash
ruff check src/
ruff format src/
```

## Troubleshooting

### GitHub CLI not found

Ensure `gh` is installed and in your PATH:

```bash
gh --version
```

### Authentication failed

Re-authenticate with GitHub CLI:

```bash
gh auth login
gh auth status
```

### Rate limiting

For large repositories, you may hit API rate limits. Use `--limit` to fetch fewer issues:

```bash
gh-org-sync sync owner/repo --limit 100
```

### File permissions

The tool creates backups by default. Ensure you have write permission to the output directory.

## License

MIT

## Related

- [Org-mode Manual](https://orgmode.org/manual/)
- [GitHub CLI](https://cli.github.com/)
- [Gitea API](https://docs.gitea.com/development/api-usage)
