"""
Main sync orchestrator.

This module coordinates the sync process:
1. Fetch issues from a provider (GitHub or Gitea)
2. Parse existing Org file
3. Merge changes
4. Write updated Org file
"""

import asyncio
import logging
from pathlib import Path

from .exceptions import InvalidRepositoryError
from .github_client import GitHubClient
from .merger import OrgMerger
from .models import MergeResult, SyncConfig
from .org_parser import OrgParser
from .org_writer import OrgWriter
from .provider import IssueProvider

logger = logging.getLogger(__name__)


class IssueSync:
    """
    Orchestrates the sync between issue providers and Org-mode files.

    This is the main entry point for sync operations, coordinating
    the issue provider, parser, merger, and writer components.
    """

    def __init__(
        self,
        provider: IssueProvider | None = None,
        timeout: int = 60,
        add_link_tag: bool = True,
    ) -> None:
        """
        Initialize the sync orchestrator.

        Args:
            provider: Issue provider (GitHub or Gitea client).
                     If None, defaults to GitHubClient.
            timeout: Timeout for API calls in seconds (used if provider is None)
            add_link_tag: Whether to add :LINK: tag to issues
        """
        self.provider = provider if provider else GitHubClient(timeout=timeout)
        self.parser = OrgParser()
        self.merger = OrgMerger(add_link_tag=add_link_tag)
        self.writer = OrgWriter(add_link_tag=add_link_tag)
        self.add_link_tag = add_link_tag

    def _validate_repo(self, repo: str) -> None:
        """Validate repository format."""
        if "/" not in repo or repo.count("/") != 1:
            raise InvalidRepositoryError(repo)

        owner, name = repo.split("/")
        if not owner or not name:
            raise InvalidRepositoryError(repo)

    async def sync(
        self,
        repo: str,
        output_file: str | Path,
        state_filter: str = "all",
        limit: int | None = None,
        include_comments: bool = True,
        dry_run: bool = False,
        backup: bool = True,
    ) -> MergeResult:
        """
        Sync GitHub issues to an Org-mode file.

        This is the main sync method that:
        1. Validates inputs
        2. Fetches issues from GitHub
        3. Parses the existing Org file (if any)
        4. Merges changes
        5. Writes the updated file

        Args:
            repo: Repository in owner/repo format
            output_file: Path to the Org output file
            state_filter: Filter issues by state ('open', 'closed', 'all')
            limit: Maximum number of issues to fetch
            include_comments: Whether to include issue comments
            dry_run: If True, don't write changes (just report what would happen)
            backup: If True, backup existing file before writing

        Returns:
            MergeResult with statistics about the sync

        Raises:
            InvalidRepositoryError: If repo format is invalid
            GitHubClientError: If GitHub API fails
            OrgFileError: If file operations fail
        """
        # Validate inputs
        self._validate_repo(repo)
        output_path = Path(output_file)

        logger.info(f"Starting sync: {repo} -> {output_path}")
        logger.info(f"Options: state={state_filter}, limit={limit}, comments={include_comments}")

        # Fetch issues from provider
        provider_name = self.provider.provider_type.value.title()
        logger.info(f"Fetching issues from {provider_name}...")
        issues = await self.provider.fetch_issues(
            repo=repo,
            state=state_filter,
            limit=limit,
            include_comments=include_comments,
        )
        logger.info(f"Fetched {len(issues)} issues from {provider_name}")

        # Parse existing Org file
        existing_headings = []
        if output_path.exists():
            logger.info(f"Parsing existing file: {output_path}")
            existing_headings = self.parser.parse_file(output_path)
            logger.info(f"Found {len(existing_headings)} existing headings")
        else:
            logger.info("No existing file, will create new")

        # Merge
        logger.info("Merging changes...")
        merged_headings, result = self.merger.merge(issues, existing_headings)

        if dry_run:
            logger.info("Dry run - not writing changes")
            return result

        # Write output
        if result.has_changes or not output_path.exists():
            logger.info(f"Writing {len(merged_headings)} headings to {output_path}")

            header = self.writer.format_file_header(
                title=f"GitHub Issues: {repo}",
                repo=repo,
            )

            self.writer.write_file(
                headings=merged_headings,
                path=output_path,
                header=header,
                backup=backup,
            )
        else:
            logger.info("No changes to write")

        return result

    async def sync_from_config(self, config: SyncConfig) -> MergeResult:
        """
        Sync using a SyncConfig object.

        Args:
            config: Sync configuration

        Returns:
            MergeResult with sync statistics
        """
        state_filter = config.state_filter
        if hasattr(state_filter, "value"):
            state_filter = state_filter.value

        return await self.sync(
            repo=config.repo,
            output_file=config.output_file,
            state_filter=str(state_filter),
            limit=config.limit,
            include_comments=config.include_comments,
            dry_run=config.dry_run,
            backup=config.backup,
        )


def run_sync(
    repo: str,
    output_file: str | Path,
    state_filter: str = "all",
    limit: int | None = None,
    include_comments: bool = True,
    dry_run: bool = False,
    backup: bool = True,
    timeout: int = 60,
    provider: IssueProvider | None = None,
) -> MergeResult:
    """
    Synchronous wrapper for IssueSync.sync().

    This is a convenience function for running sync from non-async code.

    Args:
        repo: Repository in owner/repo format
        output_file: Path to the Org output file
        state_filter: Filter issues by state
        limit: Maximum issues to fetch
        include_comments: Include issue comments
        dry_run: Don't write changes
        backup: Backup existing file
        timeout: API timeout (used if provider is None)
        provider: Issue provider (GitHub or Gitea client)

    Returns:
        MergeResult with sync statistics
    """
    syncer = IssueSync(provider=provider, timeout=timeout)
    return asyncio.run(
        syncer.sync(
            repo=repo,
            output_file=output_file,
            state_filter=state_filter,
            limit=limit,
            include_comments=include_comments,
            dry_run=dry_run,
            backup=backup,
        )
    )
