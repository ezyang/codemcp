#!/usr/bin/env python3

import logging
import os

from ..common import normalize_file_path
from ..git import commit_changes, is_git_repository
from ..shell import run_command

__all__ = [
    "chmod_exec",
]


async def chmod_exec(
    path: str,
    description: str,
    chat_id: str = None,
) -> str:
    """Make a file executable by running chmod a+x on it.

    Args:
        path: The path to the file to make executable
        description: A short description of why the file is being made executable
        chat_id: The unique ID of the current chat session

    Returns:
        A string containing the result of the operation
    """
    try:
        # Normalize the file path
        full_file_path = normalize_file_path(path)

        # Verify the file exists
        if not os.path.exists(full_file_path):
            raise FileNotFoundError(f"File does not exist: {path}")

        # Verify it's a file, not a directory
        if not os.path.isfile(full_file_path):
            raise IsADirectoryError(f"Path is a directory, not a file: {path}")

        # Get the directory containing the file for git operations
        file_dir = os.path.dirname(full_file_path)

        # Run chmod a+x on the file
        logging.info(f"Making file executable: {full_file_path}")
        await run_command(
            ["chmod", "a+x", full_file_path],
            check=True,
            capture_output=True,
            text=True,
        )

        # If this is a git repository, commit the change
        is_git_repo = await is_git_repository(file_dir)
        if is_git_repo:
            commit_message = (
                f"Make {os.path.basename(full_file_path)} executable: {description}"
            )
            success, commit_result = await commit_changes(
                file_dir, commit_message, chat_id, commit_all=True
            )
            if success:
                return f"Successfully made {os.path.basename(full_file_path)} executable and committed the change."
            else:
                return f"Successfully made {os.path.basename(full_file_path)} executable but failed to commit the change: {commit_result}"

        return f"Successfully made {os.path.basename(full_file_path)} executable."

    except Exception as e:
        error_msg = f"Error making file executable: {e}"
        logging.error(error_msg)
        raise
