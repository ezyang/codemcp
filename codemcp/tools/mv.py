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
    "mv_file",
    "mv_tool",
]


async def mv_file(
    source_path: str,
    target_path: str,
    description: str,
    chat_id: str = "",
) -> str:
    """Move a file using git mv.

    Args:
        source_path: The path to the source file to move (can be absolute or relative to repository root)
        target_path: The path to the target location (can be absolute or relative to repository root)
        description: Short description of why the file is being moved
        chat_id: The unique ID of the current chat session

    Returns:
        A string containing the result of the move operation
    """
    # Use the directory from the path as our starting point for source
    source_path = normalize_file_path(source_path)
    source_dir_path = (
        os.path.dirname(source_path) if os.path.dirname(source_path) else "."
    )

    # Normalize target path as well
    target_path = normalize_file_path(target_path)

    # Validations for source file
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    if not os.path.isfile(source_path):
        raise ValueError(f"Source path is not a file: {source_path}")

    # Get git repository root
    git_root = await get_repository_root(source_dir_path)
    # Ensure paths are absolute and resolve any symlinks
    source_path_resolved = os.path.realpath(source_path)
    git_root_resolved = os.path.realpath(git_root)
    target_path_resolved = (
        os.path.realpath(target_path)
        if os.path.exists(os.path.dirname(target_path))
        else target_path
    )

    # Use pathlib to check if the source file is within the git repo
    # This handles path traversal correctly on all platforms
    try:
        # Convert to Path objects
        source_path_obj = pathlib.Path(source_path_resolved)
        git_root_obj = pathlib.Path(git_root_resolved)

        # Check if file is inside the git repo using Path.relative_to
        # This will raise ValueError if source_path is not inside git_root
        source_path_obj.relative_to(git_root_obj)
    except ValueError:
        msg = (
            f"Source path {source_path} is not within the git repository at {git_root}"
        )
        logging.error(msg)
        raise ValueError(msg)

    # Check if target directory exists and is within the git repo
    target_dir = os.path.dirname(target_path)
    if target_dir and not os.path.exists(target_dir):
        raise FileNotFoundError(f"Target directory does not exist: {target_dir}")

    try:
        # Convert to Path objects
        target_dir_obj = pathlib.Path(
            os.path.realpath(target_dir) if target_dir else git_root_resolved
        )
        # Check if target directory is inside the git repo
        target_dir_obj.relative_to(git_root_obj)
    except ValueError:
        msg = f"Target directory {target_dir} is not within the git repository at {git_root}"
        logging.error(msg)
        raise ValueError(msg)

    # Get the relative paths using pathlib
    source_rel_path = os.path.relpath(source_path_resolved, git_root_resolved)
    target_rel_path = os.path.relpath(
        target_path_resolved
        if os.path.exists(os.path.dirname(target_path))
        else os.path.join(git_root_resolved, os.path.basename(target_path)),
        git_root_resolved,
    )

    logging.info(f"Using relative paths: {source_rel_path} -> {target_rel_path}")

    # Check if the source file is tracked by git from the git root
    await run_command(
        ["git", "ls-files", "--error-unmatch", source_rel_path],
        cwd=git_root_resolved,
        check=True,
        capture_output=True,
        text=True,
    )

    # If we get here, the file is tracked by git, so we can move it
    await run_command(
        ["git", "mv", source_rel_path, target_rel_path],
        cwd=git_root_resolved,
        check=True,
        capture_output=True,
        text=True,
    )

    # Commit the changes
    logging.info(f"Committing move of file: {source_rel_path} -> {target_rel_path}")
    success, commit_message = await commit_changes(
        git_root_resolved,
        f"Move {source_rel_path} -> {target_rel_path}: {description}",
        chat_id,
        commit_all=False,  # No need for commit_all since git mv already stages the change
    )

    if success:
        return f"Successfully moved file from {source_rel_path} to {target_rel_path}."
    else:
        return f"File was moved from {source_rel_path} to {target_rel_path} but failed to commit: {commit_message}"


@mcp.tool()
async def mv_tool(
    ctx: Context, source_path: str, target_path: str, description: str
) -> str:
    """Moves a file using git mv and commits the change.
    Provide a short description of why the file is being moved.

    Before using this tool:
    1. Ensure the source file exists and is tracked by git
    2. Ensure the target directory exists within the git repository
    3. Provide a meaningful description of why the file is being moved

    Args:
        source_path: The path to the file to move (can be relative to the project root or absolute)
        target_path: The destination path where the file should be moved to (can be relative to the project root or absolute)
        description: Short description of why the file is being moved
    """
    # Get chat ID from context
    chat_id = get_chat_id_from_context(ctx)
    return await mv_file(source_path, target_path, description, chat_id)
