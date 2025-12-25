"""
Command-line interface for gh-org-sync.

This module provides the Typer-based CLI for syncing GitHub/Gitea issues
to Org-mode files.
"""

import asyncio
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .exceptions import GitHubOrgSyncError
from .gitea_client import GiteaClient
from .github_client import GitHubClient
from .models import MergeResult
from .provider import IssueProvider
from .sync import IssueSync

# Create Typer app
app = typer.Typer(
    name="gh-org-sync",
    help="Sync GitHub issues to Org-mode files",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()
error_console = Console(stderr=True)


class StateFilter(str, Enum):
    """Issue state filter options."""

    ALL = "all"
    OPEN = "open"
    CLOSED = "closed"


class ProviderChoice(str, Enum):
    """Issue provider options."""

    GITHUB = "github"
    GITEA = "gitea"


class LogLevel(str, Enum):
    """Log level options."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def _create_provider(
    provider_choice: ProviderChoice,
    gitea_url: str | None,
    gitea_token: str | None,
    timeout: int,
) -> IssueProvider:
    """Create the appropriate issue provider based on choice."""
    if provider_choice == ProviderChoice.GITEA:
        if not gitea_url:
            raise typer.BadParameter(
                "--gitea-url is required when using Gitea provider"
            )
        token = gitea_token or os.environ.get("GITEA_TOKEN", "")
        if not token:
            raise typer.BadParameter(
                "--gitea-token is required when using Gitea provider "
                "(or set GITEA_TOKEN environment variable)"
            )
        return GiteaClient(base_url=gitea_url, token=token, timeout=timeout)
    return GitHubClient(timeout=timeout)


def setup_logging(level: LogLevel, verbose: bool = False) -> None:
    """Configure logging with Rich handler."""
    log_level = getattr(logging, level.value.upper())

    if verbose:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=error_console, show_time=False, show_path=False)],
    )


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"gh-org-sync version {__version__}")
        raise typer.Exit


@app.command()
def sync(
    repo: Annotated[
        str,
        typer.Argument(
            help="Repository in owner/repo format",
            show_default=False,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "-o",
            "--output",
            help="Output Org file path",
            show_default=False,
        ),
    ] = Path("issues.org"),
    state: Annotated[
        StateFilter,
        typer.Option(
            "-s",
            "--state",
            help="Filter by issue state",
        ),
    ] = StateFilter.ALL,
    limit: Annotated[
        int | None,
        typer.Option(
            "-l",
            "--limit",
            help="Maximum number of issues to fetch",
            min=1,
        ),
    ] = None,
    no_comments: Annotated[
        bool,
        typer.Option(
            "--no-comments",
            help="Don't include issue comments",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would happen without making changes",
        ),
    ] = False,
    no_backup: Annotated[
        bool,
        typer.Option(
            "--no-backup",
            help="Don't create backup of existing file",
        ),
    ] = False,
    no_link_tag: Annotated[
        bool,
        typer.Option(
            "--no-link-tag",
            help="Don't add :LINK: tag to headings",
        ),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="API timeout in seconds",
            min=10,
            max=300,
        ),
    ] = 60,
    provider: Annotated[
        ProviderChoice,
        typer.Option(
            "-p",
            "--provider",
            help="Issue provider (github or gitea)",
        ),
    ] = ProviderChoice.GITHUB,
    gitea_url: Annotated[
        str | None,
        typer.Option(
            "--gitea-url",
            help="Gitea server URL (e.g., https://gitea.example.com)",
            envvar="GITEA_URL",
        ),
    ] = None,
    gitea_token: Annotated[
        str | None,
        typer.Option(
            "--gitea-token",
            help="Gitea API token (or set GITEA_TOKEN env var)",
            envvar="GITEA_TOKEN",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "-v",
            "--verbose",
            help="Enable verbose output",
        ),
    ] = False,
    log_level: Annotated[
        LogLevel,
        typer.Option(
            "--log-level",
            help="Set log level",
        ),
    ] = LogLevel.INFO,
    _version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = None,
) -> None:
    """
    Sync issues to an Org-mode file.

    This command fetches issues from a GitHub or Gitea repository and
    updates an Org-mode file with the current state. User additions
    to the Org file are preserved.

    Examples:

        gh-org-sync owner/repo

        gh-org-sync owner/repo -o todos.org -s open

        gh-org-sync owner/repo --limit 50 --dry-run

        gh-org-sync owner/repo --provider gitea --gitea-url https://gitea.example.com
    """
    setup_logging(log_level, verbose)

    if dry_run:
        console.print("[yellow]Dry run mode - no changes will be written[/yellow]")

    provider_name = provider.value.title()
    console.print(f"Syncing [bold]{repo}[/bold] from {provider_name} -> [bold]{output}[/bold]")

    issue_provider: IssueProvider | None = None
    try:
        # Create the appropriate provider
        issue_provider = _create_provider(provider, gitea_url, gitea_token, timeout)

        syncer = IssueSync(
            provider=issue_provider,
            timeout=timeout,
            add_link_tag=not no_link_tag,
        )

        result = asyncio.run(
            syncer.sync(
                repo=repo,
                output_file=output,
                state_filter=state.value,
                limit=limit,
                include_comments=not no_comments,
                dry_run=dry_run,
                backup=not no_backup,
            )
        )

        # Display results
        _display_result(result, dry_run)

        if result.errors:
            raise typer.Exit(1)

    except GitHubOrgSyncError as e:
        error_console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            error_console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        error_console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130) from None
    finally:
        # Close provider if it has a close method
        if issue_provider is not None:
            asyncio.run(issue_provider.close())


@app.command()
def check(
    provider: Annotated[
        ProviderChoice,
        typer.Option(
            "-p",
            "--provider",
            help="Issue provider to check (github or gitea)",
        ),
    ] = ProviderChoice.GITHUB,
    gitea_url: Annotated[
        str | None,
        typer.Option(
            "--gitea-url",
            help="Gitea server URL (required for gitea provider)",
            envvar="GITEA_URL",
        ),
    ] = None,
    gitea_token: Annotated[
        str | None,
        typer.Option(
            "--gitea-token",
            help="Gitea API token (or set GITEA_TOKEN env var)",
            envvar="GITEA_TOKEN",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed status"),
    ] = False,
) -> None:
    """
    Check environment and provider status.

    Verifies that the provider (GitHub CLI or Gitea server) is accessible
    and authenticated.
    """
    setup_logging(LogLevel.INFO, verbose)

    provider_name = provider.value.title()
    issue_provider: IssueProvider | None = None

    with console.status(f"Checking {provider_name} connection..."):
        try:
            if provider == ProviderChoice.GITHUB:
                client = GitHubClient()
                # Check gh CLI
                asyncio.run(client.check_cli_available())
                console.print("[green]✓[/green] GitHub CLI (gh) is installed")

                # Check authentication
                asyncio.run(client.check_auth())
                console.print("[green]✓[/green] GitHub CLI is authenticated")
            else:
                # Gitea
                issue_provider = _create_provider(provider, gitea_url, gitea_token, 30)
                asyncio.run(issue_provider.check_connection())
                console.print(f"[green]✓[/green] Connected to Gitea at {gitea_url}")
                console.print("[green]✓[/green] Gitea authentication valid")

            console.print(f"\n[green]All {provider_name} checks passed![/green]")

        except GitHubOrgSyncError as e:
            error_console.print(f"[red]✗[/red] {e.message}")
            if e.hint:
                error_console.print(f"  [dim]Hint: {e.hint}[/dim]")
            raise typer.Exit(1) from None
        finally:
            if issue_provider is not None:
                asyncio.run(issue_provider.close())


@app.command()
def parse(
    file: Annotated[
        Path,
        typer.Argument(help="Org file to parse"),
    ],
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed output"),
    ] = False,
) -> None:
    """
    Parse an Org file and display its structure.

    Useful for debugging and verifying file format.
    """
    setup_logging(LogLevel.INFO, verbose)

    if not file.exists():
        error_console.print(f"[red]Error:[/red] File not found: {file}")
        raise typer.Exit(1)

    from .org_parser import OrgParser, collect_all_headings

    parser = OrgParser()
    headings = parser.parse_file(file)

    if not headings:
        console.print("[yellow]No headings found in file[/yellow]")
        raise typer.Exit(0)

    # Create table
    table = Table(title=f"Org File: {file}")
    table.add_column("#", style="dim")
    table.add_column("Level", justify="center")
    table.add_column("State", justify="center")
    table.add_column("Title")
    table.add_column("GitHub #", justify="right")
    table.add_column("Tags")

    all_headings = collect_all_headings(headings)

    for i, heading in enumerate(all_headings, 1):
        level = "*" * heading.level
        state = heading.todo_state.value if heading.todo_state else "-"
        gh_num = heading.github_number
        gh_str = str(gh_num) if gh_num else "-"
        tags = ":".join(heading.tags) if heading.tags else "-"

        # Truncate long titles
        title = heading.title
        if len(title) > 50:
            title = title[:47] + "..."

        table.add_row(
            str(i),
            level,
            state,
            title,
            gh_str,
            tags,
        )

    console.print(table)

    # Summary
    github_linked = sum(1 for h in all_headings if h.is_github_synced)
    user_created = len(all_headings) - github_linked

    console.print(f"\nTotal: {len(all_headings)} headings")
    console.print(f"  GitHub-linked: {github_linked}")
    console.print(f"  User-created: {user_created}")


def _display_result(result: MergeResult, dry_run: bool) -> None:
    """Display sync result as a formatted table."""
    action_word = "Would sync" if dry_run else "Synced"

    # Summary panel
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()

    summary.add_row("GitHub issues:", str(result.total_github_issues))
    summary.add_row("Org headings:", str(result.total_org_headings))
    summary.add_row("Added:", f"[green]{result.added}[/green]")
    summary.add_row("Updated:", f"[yellow]{result.updated}[/yellow]")
    summary.add_row("Unchanged:", str(result.unchanged))
    summary.add_row("Preserved:", f"[blue]{result.preserved}[/blue]")

    if result.errors:
        summary.add_row("Errors:", f"[red]{len(result.errors)}[/red]")

    panel = Panel(
        summary,
        title=f"{action_word} Results",
        border_style="green" if not result.errors else "yellow",
    )
    console.print(panel)

    # Show errors if any
    if result.errors:
        error_console.print("\n[red]Errors:[/red]")
        for error in result.errors[:10]:
            error_console.print(f"  - {error}")
        if len(result.errors) > 10:
            error_console.print(f"  ... and {len(result.errors) - 10} more")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
