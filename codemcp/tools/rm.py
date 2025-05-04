#!/usr/bin/env python3

import logging
import os
import pathlib

from mcp.server.fastmcp import Context

from ..common import normalize_file_path
from ..git import commit_changes, get_repository_root
from ..main import get_chat_id_from_context, mcp
from ..shell import run_command

__all__ = [
    "rm_file",
    "rm_tool",
]


async def rm_file(
    path: str,
    description: str,
    chat_id: str = "",
) -> str:
    """Remove a file using git rm.

    Args:
        path: The path to the file to remove (can be absolute or relative to repository root)
        description: Short description of why the file is being removed
        chat_id: The unique ID of the current chat session

    Returns:
        A string containing the result of the removal operation
    """
    # Use the directory from the path as our starting point
    file_path = normalize_file_path(path)
    dir_path = os.path.dirname(file_path) if os.path.dirname(file_path) else "."

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File does not exist: {path}")

    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {path}")

    # Get git repository root
    git_root = await get_repository_root(dir_path)
    # Ensure paths are absolute and resolve any symlinks
    file_path_resolved = os.path.realpath(file_path)
    git_root_resolved = os.path.realpath(git_root)

    # Use pathlib to check if the file is within the git repo
    # This handles path traversal correctly on all platforms
    try:
        # Convert to Path objects
        file_path_obj = pathlib.Path(file_path_resolved)
        git_root_obj = pathlib.Path(git_root_resolved)

        # Check if file is inside the git repo using Path.relative_to
        # This will raise ValueError if file_path is not inside git_root
        file_path_obj.relative_to(git_root_obj)
    except ValueError:
        msg = f"Path {file_path} is not within the git repository at {git_root}"
        logging.error(msg)
        raise ValueError(msg)

    # Get the relative path using pathlib
    rel_path = os.path.relpath(file_path_resolved, git_root_resolved)
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

    # Commit the changes
    logging.info(f"Committing removal of file: {rel_path}")
    success, commit_message = await commit_changes(
        git_root_resolved,
        f"Remove {rel_path}: {description}",
        chat_id,
        commit_all=False,  # No need for commit_all since git rm already stages the change
    )

    if success:
        return f"Successfully removed file {rel_path}."
    else:
        return f"File {rel_path} was removed but failed to commit: {commit_message}"


@mcp.tool()
async def rm_tool(ctx: Context, path: str, description: str) -> str:
    """Removes a file using git rm and commits the change.
    Provide a short description of why the file is being removed.

    Before using this tool:
    1. Ensure the file exists and is tracked by git
    2. Provide a meaningful description of why the file is being removed

    Args:
        path: The path to the file to remove (can be relative to the project root or absolute)
        description: Short description of why the file is being removed
    """
    # Get chat ID from context
    chat_id = get_chat_id_from_context(ctx)
    return await rm_file(path, description, chat_id)
