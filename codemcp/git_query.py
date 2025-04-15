#!/usr/bin/env python3

import logging
import os
import re
import subprocess

from .shell import run_command

__all__ = [
    "get_head_commit_message",
    "get_head_commit_hash",
    "get_head_commit_chat_id",
    "get_repository_root",
    "is_git_repository",
    "get_ref_commit_chat_id",
    "find_git_root",
    "get_current_commit_hash",
]

log = logging.getLogger(__name__)


async def get_head_commit_message(directory: str) -> str:
    """Get the full commit message from HEAD.

    Args:
        directory: The directory to check

    Returns:
        The commit message

    Raises:
        subprocess.SubprocessError: If HEAD does not exist or another git error occurs
        Exception: For any other errors during the operation
    """
    # Get the commit message - this will fail if HEAD doesn't exist
    result = await run_command(
        ["git", "log", "-1", "--pretty=%B"],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    )

    return str(result.stdout.strip())


async def get_head_commit_hash(directory: str, short: bool = True) -> str:
    """Get the commit hash from HEAD.

    Args:
        directory: The directory to check
        short: Whether to get short hash (default) or full hash

    Returns:
        The commit hash

    Raises:
        subprocess.SubprocessError: If HEAD does not exist or another git error occurs
        Exception: For any other errors during the operation
    """
    # Get the commit hash (short or full)
    cmd = ["git", "rev-parse"]
    if short:
        cmd.append("--short")
    cmd.append("HEAD")

    result = await run_command(
        cmd,
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    )

    return str(result.stdout.strip())


async def get_head_commit_chat_id(directory: str) -> str | None:
    """Get the chat ID from the HEAD commit's message.

    Args:
        directory: The directory to check

    Returns:
        The chat ID if found, None otherwise

    Raises:
        subprocess.SubprocessError: If HEAD does not exist or another git error occurs
        Exception: For any other errors during the operation
    """
    commit_message = await get_head_commit_message(directory)

    # Use regex to find the last occurrence of codemcp-id: XXX
    # The pattern looks for "codemcp-id: " followed by any characters up to a newline or end of string
    matches = re.findall(r"codemcp-id:\s*([a-zA-Z0-9-]+)", commit_message)

    # Return the last match if any matches found
    if matches:
        return matches[-1].strip()
    return None


async def get_repository_root(path: str) -> str:
    """Get the root directory of the Git repository containing the path.

    This function is robust to non-existent paths. It will walk up the directory tree
    until it finds an existing directory, and then attempt to find the git repository root.

    Args:
        path: The file path to get the repository root for

    Returns:
        The absolute path to the repository root

    Raises:
        subprocess.SubprocessError: If a git command fails
        OSError: If there are file system related errors
        ValueError: If the path is not in a Git repository
    """
    # Get the absolute path to ensure consistency
    abs_path = os.path.abspath(path)

    # Get the directory containing the file or use the path itself if it's a directory
    directory = os.path.dirname(abs_path) if os.path.isfile(abs_path) else abs_path

    # Handle non-existent paths by walking up the directory tree
    # until we find an existing directory
    original_directory = directory
    while directory and not os.path.exists(directory):
        logging.debug(f"Directory doesn't exist, walking up: {directory}")
        parent = os.path.dirname(directory)
        # If we've reached the root directory and it doesn't exist, stop
        if parent == directory:
            logging.debug(f"Reached root directory and it doesn't exist: {directory}")
            raise ValueError(
                f"No existing parent directory found for path: {original_directory}"
            )
        directory = parent

    # At this point, directory exists and is the closest existing parent of the original path
    logging.debug(f"Using existing directory for git operation: {directory}")

    # Get the repository root
    result = await run_command(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    )

    return str(result.stdout.strip())


async def is_git_repository(path: str) -> bool:
    """Check if the path is within a Git repository.

    Args:
        path: The file path to check

    Returns:
        True if path is in a Git repository, False otherwise
    """
    try:
        # Try to get the repository root - this handles path existence checks
        # and directory traversal internally
        await get_repository_root(path)

        # If we get here, we found a valid git repository
        return True
    except (subprocess.SubprocessError, OSError, ValueError):
        # If we can't get the repo root, it's not a proper git repository
        # or the path doesn't exist or isn't in a repo
        return False


async def get_ref_commit_chat_id(directory: str, ref_name: str) -> str | None:
    """Get the chat ID from a specific reference's commit message.

    Args:
        directory: The directory to check
        ref_name: The reference name to check

    Returns:
        The chat ID if found, None otherwise
    """
    try:
        # Check if the reference exists
        result = await run_command(
            ["git", "show-ref", "--verify", ref_name],
            cwd=directory,
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Reference doesn't exist
            return None

        # Get the commit message from the reference
        message_result = await run_command(
            ["git", "log", "-1", "--pretty=%B", ref_name],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
        )
        commit_message = str(message_result.stdout.strip())

        # Use regex to find the last occurrence of codemcp-id: XXX
        # The pattern looks for "codemcp-id: " followed by any characters up to a newline or end of string
        matches = re.findall(r"codemcp-id:\s*([^\n]*)", commit_message)

        # Return the last match if any matches found
        if matches:
            return matches[-1].strip()
        return None
    except Exception as e:
        logging.warning(
            f"Exception when getting reference commit chat ID: {e!s}", exc_info=True
        )
        return None


def find_git_root(start_path: str) -> str | None:
    """Find the root of the Git repository starting from the given path.

    Args:
        start_path: The path to start searching from

    Returns:
        The absolute path to the Git repository root, or None if not found
    """
    path = os.path.abspath(start_path)

    while path:
        if os.path.isdir(os.path.join(path, ".git")):
            return path

        parent = os.path.dirname(path)
        if parent == path:  # Reached filesystem root
            return None

        path = parent

    return None


async def get_current_commit_hash(path: str, short: bool = True) -> str | None:
    """Get the current commit hash for the repository.

    This function is similar to get_head_commit_hash but designed to be used
    after operations to report the latest commit hash.

    Args:
        path: The path to a file or directory in the git repository
        short: Whether to get short hash (default) or full hash

    Returns:
        The current commit hash if available, None otherwise

    Raises:
        Exception: For errors that should be propagated

    Note:
        This function returns None for expected errors like non-git repositories.
        This function works with both directory and file paths.
    """
    try:
        # Get the directory - if path is a file, use its directory
        os.path.dirname(path) if os.path.isfile(path) else path

        if not await is_git_repository(path):
            return None

        # Get the repository root for more reliable operations
        try:
            git_cwd = await get_repository_root(path)
        except Exception:
            # If we can't get the repository root, it's not a valid git repository
            return None

        # Get the commit hash (short or full)
        cmd = ["git", "rev-parse"]
        if short:
            cmd.append("--short")
        cmd.append("HEAD")

        result = await run_command(
            cmd,
            cwd=git_cwd,
            check=False,  # Don't raise exception if command fails
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return str(result.stdout.strip())
        return None
    except Exception as e:
        logging.warning(
            f"Exception when getting current commit hash: {e!s}", exc_info=True
        )
        return None
