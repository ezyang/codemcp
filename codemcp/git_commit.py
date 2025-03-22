#!/usr/bin/env python3

import logging
import os
import re
import sys

from .config import get_disable_git_commit
from .git_message import (
    update_commit_message_with_description,
)
from .git_query import (
    get_head_commit_chat_id,
    get_head_commit_hash,
    get_head_commit_message,
    is_git_repository,
)
from .shell import run_command

__all__ = ["commit_changes", "create_commit_reference"]

log = logging.getLogger(__name__)


async def create_commit_reference(
    path: str,
    chat_id: str,
    commit_msg: str,
) -> tuple[str, str]:
    """Create a Git commit without advancing HEAD and store it in a reference.

    This function creates a commit using Git plumbing commands and stores it
    in a reference (refs/codemcp/<chat_id>) without changing HEAD.  We'll use
    this to make the "real" commit once our first change happens.

    Args:
        path: The path to the file or directory to commit
        chat_id: The unique ID of the current chat session
        commit_msg: Commit message

    Returns:
        A tuple of (message, commit_hash)

    Raises:
        ValueError: If the chat_id format is invalid
        FileNotFoundError: If the path doesn't exist or isn't in a Git repository
        subprocess.CalledProcessError: If a Git command fails
        Exception: For other errors during the Git operations
    """
    if not re.fullmatch(r"^[A-Za-z0-9-]+$", chat_id):
        raise ValueError(f"Invalid chat_id format: {chat_id}")

    log.debug(
        "create_commit_reference(%s, %s, %s)",
        path,
        chat_id,
        commit_msg,
    )

    # First, check if this is a git repository
    if not await is_git_repository(path):
        raise FileNotFoundError(f"Path '{path}' is not in a Git repository")

    # Get absolute paths for consistency
    abs_path = os.path.abspath(path)

    # Get the directory - if path is a file, use its directory, otherwise use the path itself
    directory = os.path.dirname(abs_path) if os.path.isfile(abs_path) else abs_path

    # Get the git repository root for more reliable operations
    from .git_query import get_repository_root

    git_cwd = await get_repository_root(directory)

    # Create the tree object for the empty commit
    # Get the tree from HEAD or create a new empty tree if no HEAD exists
    tree_hash = ""
    has_commits = False
    rev_parse_result = await run_command(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=git_cwd,
        capture_output=True,
        text=True,
        check=False,
    )

    if rev_parse_result.returncode == 0:
        has_commits = True
        tree_result = await run_command(
            ["git", "show", "-s", "--format=%T", "HEAD"],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        tree_hash = tree_result.stdout.strip()
    else:
        # Create an empty tree if no HEAD exists
        empty_tree_result = await run_command(
            ["git", "mktree"],
            cwd=git_cwd,
            input="",
            capture_output=True,
            text=True,
            check=True,
        )
        tree_hash = empty_tree_result.stdout.strip()

    commit_message = commit_msg

    # Get parent commit if we have HEAD
    parent_arg = []
    if has_commits:
        head_hash_result = await run_command(
            ["git", "rev-parse", "HEAD"],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        head_hash = head_hash_result.stdout.strip()
        parent_arg = ["-p", head_hash]

    # Create the commit object
    commit_result = await run_command(
        ["git", "commit-tree", tree_hash, *parent_arg, "-m", commit_message],
        cwd=git_cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_hash = commit_result.stdout.strip()

    ref_name = f"refs/codemcp/{chat_id}"

    # Update the reference to point to the new commit
    await run_command(
        ["git", "update-ref", ref_name, commit_hash],
        cwd=git_cwd,
        capture_output=True,
        text=True,
        check=True,
    )

    # Check if git commit is disabled
    disable_git_commit = get_disable_git_commit()
    print(
        f"DEBUG from create_commit_reference: disable_git_commit = {disable_git_commit}",
        file=sys.stderr,
    )

    if disable_git_commit:
        # Also update the virtual-head reference to point to the new commit
        virtual_head_ref = "refs/codemcp/virtual-head"
        await run_command(
            ["git", "update-ref", virtual_head_ref, commit_hash],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        print(
            f"DEBUG: Updated virtual-head reference to {commit_hash}", file=sys.stderr
        )

    return (
        f"Created commit reference {ref_name} -> {commit_hash}",
        commit_hash,
    )


async def commit_changes(
    path: str,
    description: str,
    chat_id: str,
    commit_all: bool = False,
) -> tuple[bool, str]:
    """Commit changes to a file, directory, or all files in Git.

    This function is a slight misnomer, as we may not actually create a new
    commit; we may merely amend the current commit.  The life cycle looks like this:

    1. On first write, when no commit exists: we'll cherry-pick that reference
       first to create the initial commit and then proceed with the changes.

    2. On later writes, we'll directly amend the existing commit.

    If commit_all is True, all changes in the repository will be committed.
    When commit_all is True, path can be None.

    Args:
        path: The path to the file or directory to commit
        description: Commit message describing the change
        chat_id: The unique ID of the current chat session
        commit_all: Whether to commit all changes in the repository

    Returns:
        A tuple of (success, message)

    """
    log.debug(
        "commit_changes(%s, %s, %s, commit_all=%s)",
        path,
        description,
        chat_id,
        commit_all,
    )
    # First, check if this is a git repository
    if not await is_git_repository(path):
        return False, f"Path '{path}' is not in a Git repository"

    # Get absolute paths for consistency
    abs_path = os.path.abspath(path)

    # Get the directory - if path is a file, use its directory, otherwise use the path itself
    directory = os.path.dirname(abs_path) if os.path.isfile(abs_path) else abs_path

    # If it's a file, check if it exists (only if not commit_all mode)
    if not commit_all and os.path.isfile(abs_path) and not os.path.exists(abs_path):
        return False, f"File does not exist: {abs_path}"

    # Get the git repository root for more reliable operations
    from .git_query import get_repository_root

    git_cwd = await get_repository_root(directory)

    # Handle commit_all mode
    if commit_all:
        # Check if working directory has uncommitted changes
        status_result = await run_command(
            ["git", "status", "--porcelain"],
            cwd=git_cwd,
            capture_output=True,
            check=True,
            text=True,
        )

        if status_result.stdout:
            # Add all changes to staging
            add_result = await run_command(
                ["git", "add", "."],
                cwd=git_cwd,
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            # No changes to commit
            return True, "No changes to commit"
    else:
        # Standard path-specific mode
        # Add the path to git - could be a file or directory
        try:
            # If path is a directory, do git add .
            add_command = ["git", "add", abs_path]

            add_result = await run_command(
                add_command,
                cwd=git_cwd,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e:
            return False, f"Failed to add to Git: {str(e)}"

        if add_result.returncode != 0:
            return False, f"Failed to add to Git: {add_result.stderr}"

    # Check if there are any changes to commit after git add
    diff_result = await run_command(
        ["git", "diff-index", "--cached", "--quiet", "HEAD"],
        cwd=git_cwd,
        capture_output=True,
        text=True,
        check=False,
    )

    # If diff-index returns 0, there are no changes to commit
    if diff_result.returncode == 0:
        return (
            True,
            "No changes to commit (changes already committed or no changes detected)",
        )

    # Determine whether to amend or create a new commit
    head_chat_id = await get_head_commit_chat_id(git_cwd)
    logging.debug(
        "commit_changes: head_chat_id = %s",
        head_chat_id,
    )

    verb = "amended"

    # If HEAD exists but doesn't have the right chat_id, check if we have a
    # commit reference for this chat_id that we need to cherry-pick first
    if head_chat_id != chat_id:
        verb = "committed"
        ref_name = f"refs/codemcp/{chat_id}"
        ref_exists = False

        # Check if the reference exists
        ref_result = await run_command(
            ["git", "show-ref", "--verify", ref_name],
            cwd=git_cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        ref_exists = ref_result.returncode == 0

        if ref_exists:
            # Using git plumbing commands instead of cherry-pick to avoid conflicts with local changes
            logging.info(f"Creating a new commit from reference {ref_name}")

            # Get the current HEAD commit hash
            head_hash = await get_head_commit_hash(git_cwd, short=False)

            # Get the tree from HEAD
            tree_result = await run_command(
                ["git", "show", "-s", "--format=%T", "HEAD"],
                cwd=git_cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            tree_hash = tree_result.stdout.strip()

            # Get the commit message from the reference
            ref_message_result = await run_command(
                ["git", "log", "-1", "--pretty=%B", ref_name],
                cwd=git_cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            ref_message = ref_message_result.stdout.strip()

            # Create a new commit with the same tree as HEAD but message from the reference
            # This effectively creates the commit without changing the working tree
            new_commit_result = await run_command(
                [
                    "git",
                    "commit-tree",
                    tree_hash,
                    "-p",
                    head_hash,
                    "-m",
                    ref_message,
                ],
                cwd=git_cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            new_commit_hash = new_commit_result.stdout.strip()

            # Check if git commit is disabled
            disable_git_commit = get_disable_git_commit()
            print(
                f"DEBUG from git_commit.py: disable_git_commit = {disable_git_commit}",
                file=sys.stderr,
            )
            if not disable_git_commit:
                # Update HEAD to point to the new commit
                await run_command(
                    ["git", "update-ref", "HEAD", new_commit_hash],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                )

            logging.info(f"Successfully applied reference commit for chat ID {chat_id}")
            # After applying, the HEAD commit should have the right chat_id
            head_chat_id = await get_head_commit_chat_id(git_cwd)

    # When disable_git_commit=True, we need to check for the case where we're operating
    # with the virtual-head reference not yet created or not having the right chat_id
    disable_git_commit = get_disable_git_commit()
    if disable_git_commit and head_chat_id != chat_id:
        # Let's manually verify if we can find a reference for this chat_id
        ref_name = f"refs/codemcp/{chat_id}"
        ref_exists = False
        try:
            ref_result = await run_command(
                ["git", "show-ref", "--verify", ref_name],
                cwd=git_cwd,
                check=False,
                capture_output=True,
                text=True,
            )
            ref_exists = ref_result.returncode == 0
        except Exception:
            ref_exists = False

        if ref_exists:
            # Set up virtual-head to point to this reference commit
            virtual_head_ref = "refs/codemcp/virtual-head"
            ref_commit = await run_command(
                ["git", "rev-parse", ref_name],
                cwd=git_cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            ref_commit_hash = ref_commit.stdout.strip()

            # Update the virtual-head reference
            await run_command(
                ["git", "update-ref", virtual_head_ref, ref_commit_hash],
                cwd=git_cwd,
                capture_output=True,
                text=True,
                check=True,
            )

            # Update the head_chat_id
            head_chat_id = chat_id

            print(
                f"DEBUG: Set up virtual-head to point to {ref_name} -> {ref_commit_hash}",
                file=sys.stderr,
            )

    assert head_chat_id == chat_id, (
        "This usually fails because you didn't InitProject before interacting with codemcp"
    )

    # Get the current commit hash before amending
    commit_hash = await get_head_commit_hash(git_cwd)

    # Get the current commit message
    current_commit_message = await get_head_commit_message(git_cwd)

    # Verify the commit has our codemcp-id
    if chat_id and "codemcp-id: " not in current_commit_message:
        logging.warning("Expected codemcp-id in current commit but not found")

    # Use the update function for subsequent edits
    commit_message = update_commit_message_with_description(
        current_commit_message=current_commit_message,
        description=description,
        commit_hash=commit_hash,
    )

    # Check if git commit is disabled
    disable_git_commit = get_disable_git_commit()
    print(
        f"DEBUG from git_commit.py (second location): disable_git_commit = {disable_git_commit}",
        file=sys.stderr,
    )

    if disable_git_commit:
        # Create a new commit object without updating HEAD
        # First, get the current tree
        tree_result = await run_command(
            ["git", "write-tree"],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        tree_hash = tree_result.stdout.strip()

        # Get parent (current HEAD)
        head_hash_result = await run_command(
            ["git", "rev-parse", "HEAD"],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        head_hash = head_hash_result.stdout.strip()

        # Create a new commit without changing HEAD
        commit_result = await run_command(
            ["git", "commit-tree", tree_hash, "-p", head_hash, "-m", commit_message],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        # Amend the previous commit normally
        commit_result = await run_command(
            ["git", "commit", "--amend", "-m", commit_message],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=False,
        )

    if commit_result.returncode != 0:
        return False, f"Failed to commit changes: {commit_result.stderr}"

    new_commit_hash = ""
    if disable_git_commit:
        # When using commit-tree, the output is the new commit hash
        new_commit_hash = commit_result.stdout.strip()

        # Store the commit in the reference for this chat_id
        ref_name = f"refs/codemcp/{chat_id}"
        await run_command(
            ["git", "update-ref", ref_name, new_commit_hash],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=True,
        )

        # Also create/update a special virtual HEAD reference
        virtual_head_ref = "refs/codemcp/virtual-head"
        await run_command(
            ["git", "update-ref", virtual_head_ref, new_commit_hash],
            cwd=git_cwd,
            capture_output=True,
            text=True,
            check=True,
        )

        # Modified success message for disable_git_commit mode
        return (
            True,
            f"Changes {verb} successfully without updating working tree (previous commit was {commit_hash}, new commit is {new_commit_hash})",
        )
    else:
        # If this was a normal amended commit, include the original hash in the message
        return (
            True,
            f"Changes {verb} successfully (previous commit was {commit_hash})",
        )
