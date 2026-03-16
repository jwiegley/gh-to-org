# gh-org-sync

I've been tracking GitHub issues in Org-mode for a while now, and got tired of
manually copying things back and forth. `gh-org-sync` is a CLI tool that
fetches issues from GitHub (or Gitea) and formats them as proper Org headings
-- complete with properties drawers, timestamps, labels-as-tags, and threaded
comments.

The thing that makes it actually useful beyond a simple dump is the merging:
you can re-sync at any time and it'll update what changed on GitHub while
leaving your local notes, extra properties, and manually-added headings alone.

## Getting started

You'll need the [GitHub CLI](https://cli.github.com/) installed and
authenticated:

```bash
gh auth login
```

### Install with Nix

```bash
nix build
nix profile install .
```

### Install with pip

```bash
pip install .
```

### Basic usage

```bash
# Sync all issues from a repo
gh-org-sync sync owner/repo

# Only open issues, to a specific file
gh-org-sync sync owner/repo -s open -o my-issues.org

# Dry run to see what would happen
gh-org-sync sync owner/repo --dry-run
```

There's also a `check` command to verify your credentials are working, and a
`parse` command that's handy for debugging Org file structure.

## How the merging works

Issues are matched by their `GITHUB_NUMBER` property in the Org file. On each
sync:

- New issues get appended
- Existing issues are updated in-place (title, body, state, labels, comments)
- Your additions -- extra tags, custom properties, child headings, notes after
  the sync marker -- are all preserved
- Headings without a `GITHUB_NUMBER` aren't touched at all

So you can freely add your own notes, refile things, change tags, and none of
that gets blown away on the next sync.

## Gitea support

```bash
export GITEA_URL=https://gitea.example.com
export GITEA_TOKEN=your_token

gh-org-sync sync owner/repo --provider gitea
```

## What the output looks like

```org
* TODO Fix authentication bug :LINK:bug:urgent:
:PROPERTIES:
:AUTHOR:         johndoe
:CREATED:        [2024-01-15 Mon 10:30]
:GITHUB_NUMBER:  123
:GITHUB_STATE:   open
:URL:            https://github.com/owner/repo/issues/123
:END:

Users cannot log in when using SSO.

** Comment by @developer [2024-01-15 Mon 14:00]
Investigating the issue.
```

Markdown in issue bodies and comments gets converted to Org syntax
automatically -- links, emphasis, code blocks, quotes, the works.

## Development

```bash
nix develop          # enter dev shell with all deps
pytest               # run tests
mypy src/            # type check
ruff check .         # lint
ruff format .        # format
nix flake check      # run all checks at once
```

Pre-commit hooks are configured via [lefthook](https://github.com/evilmartians/lefthook).
After entering the dev shell, `lefthook install` sets them up.

## License

BSD 3-Clause. See [LICENSE.md](LICENSE.md).
