#!/usr/bin/env python3

import logging
import os
import pathlib
from typing import Optional

from ..access import check_edit_permission
from ..common import normalize_file_path
from ..git import commit_changes, get_repository_root, is_git_repository
from ..mcp import mcp
from ..shell import run_command
from .commit_utils import append_commit_hash

__all__ = [
    "rm",
]


@mcp.tool()
async def rm(
    path: str, description: str, chat_id: str, commit_hash: Optional[str] = None,
    no_commit: bool = True,
) -> str:
    """Removes a file using git rm and commits the change.
    Provide a short description of why the file is being removed.

    Before using this tool:
    1. Ensure the file exists and is tracked by git
    2. Provide a meaningful description of why the file is being removed

    Args:
        path: The path to the file to remove (can be relative to the project root or absolute)
        description: Short description of why the file is being removed
        chat_id: The unique ID to identify the chat session
        commit_hash: Optional Git commit hash for version tracking
        no_commit: Whether to skip creating a git commit (default: True)

    Returns:
        A success message

    """
    # Normalize the file path
    full_path = normalize_file_path(path)

    # Validate the file path
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File does not exist: {path}")

    # Safety check: Verify the file is within a git repository with codemcp.toml
    if not await is_git_repository(os.path.dirname(full_path)):
        raise ValueError(f"File is not in a Git repository: {path}")

    # Check edit permission (which verifies codemcp.toml exists)
    is_permitted, permission_message = await check_edit_permission(full_path)
    if not is_permitted:
        raise ValueError(permission_message)

    # Determine if it's a file or directory
    os.path.isdir(full_path)

    # Get git repository root
    git_root = await get_repository_root(os.path.dirname(full_path))
    # Ensure paths are absolute and resolve any symlinks
    full_path_resolved = os.path.realpath(full_path)
    git_root_resolved = os.path.realpath(git_root)

    # Use pathlib to check if the file is within the git repo
    # This handles path traversal correctly on all platforms
    try:
        # Convert to Path objects
        full_path_obj = pathlib.Path(full_path_resolved)
        git_root_obj = pathlib.Path(git_root_resolved)

        # Check if file is inside the git repo using Path.relative_to
        # This will raise ValueError if full_path is not inside git_root
        full_path_obj.relative_to(git_root_obj)
    except ValueError:
        msg = f"Path {full_path} is not within the git repository at {git_root}"
        logging.error(msg)
        raise ValueError(msg)

    # Get the relative path using pathlib
    rel_path = os.path.relpath(full_path_resolved, git_root_resolved)
    logging.info(f"Using relative path: {rel_path}")

    # Check if the file is tracked by git from the git root
    await run_command(
        ["git", "ls-files", "--error-unmatch", rel_path],
        cwd=git_root_resolved,
        check=True,
        capture_output=True,
        text=True,
    )

    # If we get here, the file is tracked by git, so we can remove it
    await run_command(
        ["git", "rm", rel_path],
        cwd=git_root_resolved,
        check=True,
        capture_output=True,
        text=True,
    )

    # Commit the changes (if no_commit is False)
    logging.info(f"Committing removal of file: {rel_path}")
    success, commit_message = await commit_changes(
        git_root_resolved,
        f"Remove {rel_path}: {description}",
        chat_id,
        commit_all=False,  # No need for commit_all since git rm already stages the change
        no_commit=no_commit,
    )

    result = ""
    if success:
        result = f"Successfully removed file {rel_path}."
    else:
        result = f"File {rel_path} was removed but failed to commit: {commit_message}"

    # Append commit hash
    result, _ = await append_commit_hash(result, git_root_resolved, commit_hash)
    return result
