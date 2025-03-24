#!/usr/bin/env python3

import logging
import os

from .git_query import get_repository_root

__all__ = [
    "get_git_base_dir",
    "check_edit_permission",
]


async def get_git_base_dir(file_path: str) -> str:
    """Get the base directory of the git repository containing the file.

    Args:
        file_path: The path to the file or directory

    Returns:
        The base directory of the git repository

    Raises:
        subprocess.SubprocessError: If there's an issue with git subprocess
        OSError: If there's an issue with file operations
        ValueError: If there's an invalid path or comparison
    """
    # First normalize the path to resolve any .. or symlinks
    normalized_path = os.path.normpath(os.path.abspath(file_path))

    # Use get_repository_root which handles non-existent paths and walks up directories
    git_base_dir = await get_repository_root(normalized_path)
    logging.debug(f"Git base directory: {git_base_dir}")

    # SECURITY CHECK: Ensure file_path is within the git repository
    # This prevents path traversal across repositories

    # Handle symlinked paths (on macOS /tmp links to /private/tmp)
    normalized_git_base = os.path.normpath(os.path.realpath(git_base_dir))
    normalized_path = os.path.normpath(os.path.realpath(normalized_path))

    # Perform path traversal check - ensure target path is inside git repo
    # Check if the path is within the git repo by calculating the relative path
    rel_path = os.path.relpath(normalized_path, normalized_git_base)

    # If the relative path starts with "..", it's outside the git repo
    if rel_path.startswith("..") or rel_path == "..":
        logging.debug(
            f"Path traversal check: {normalized_path} is outside git repo {normalized_git_base}"
        )

        # Special case: On macOS, check for /private/tmp vs /tmp differences
        # If either path contains the other after normalization, they might be the same location
        if (
            normalized_git_base in normalized_path
            or normalized_path in normalized_git_base
        ):
            logging.debug(
                f"Path might be the same location after symlinks: {normalized_path}, {normalized_git_base}"
            )
        else:
            logging.warning(
                f"File path {file_path} is outside git repository {git_base_dir}"
            )
            raise ValueError(
                f"File path {file_path} is outside git repository {git_base_dir}"
            )

    return git_base_dir


async def check_edit_permission(file_path: str) -> tuple[bool, str]:
    """Check if editing the file is permitted based on the presence of codemcp.toml
    in the git repository's root directory.

    Args:
        file_path: The path to the file to edit

    Returns:
        A tuple of (is_permitted, message)

    Raises:
        subprocess.SubprocessError: If there's an issue with git subprocess
        OSError: If there's an issue with file operations
        ValueError: If file_path is not in a git repository or other path issues
    """
    # Get the git base directory (will raise an exception if not in a git repo)
    git_base_dir = await get_git_base_dir(file_path)

    # Check for codemcp.toml in the git base directory
    config_path = os.path.join(git_base_dir, "codemcp.toml")
    if not os.path.exists(config_path):
        return False, (
            "Permission denied: codemcp.toml file not found in the git repository root. "
            "Please create a codemcp.toml file in the root directory of your project "
            "to enable editing files with codemcp."
        )

    return True, "Permission granted."
