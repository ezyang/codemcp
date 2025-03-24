#!/usr/bin/env python3

import asyncio
import logging
import os

import anyio

from .access import check_edit_permission
from .git import commit_changes
from .line_endings import apply_line_endings, normalize_to_lf

__all__ = [
    "check_file_path_and_permissions",
    "check_git_tracking_for_existing_file",
    "ensure_directory_exists",
    "write_text_content",
    "async_open_text",
]


async def check_file_path_and_permissions(file_path: str) -> tuple[bool, str | None]:
    """Check if the file path is valid and has the necessary permissions.

    Args:
        file_path: The absolute path to the file

    Returns:
        A tuple of (is_valid, error_message)
        If is_valid is True, error_message will be None

    """
    # Check that the path is absolute
    if not os.path.isabs(file_path):
        return False, f"File path must be absolute, not relative: {file_path}"

    # Check if we have permission to edit this file
    is_permitted, permission_message = await check_edit_permission(file_path)
    if not is_permitted:
        return False, permission_message

    return True, None


async def check_git_tracking_for_existing_file(
    file_path: str,
    chat_id: str,
) -> tuple[bool, str | None]:
    """Check if an existing file is tracked by git. Skips check for non-existent files.

    Args:
        file_path: The absolute path to the file
        chat_id: The unique ID to identify the chat session

    Returns:
        A tuple of (success, error_message)
        If success is True, error_message will be None

    """
    # Check if the file exists
    file_exists = os.path.exists(file_path)

    if file_exists:
        # Check if the file is tracked by git - use ls-files directly since we just need to check tracking
        directory = os.path.dirname(file_path)

        # Check if the file is tracked by git
        from .shell import run_command

        file_status = await run_command(
            ["git", "ls-files", "--error-unmatch", file_path],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )

        file_is_tracked = file_status.returncode == 0

        # If the file is not tracked, return an error
        if not file_is_tracked:
            error_msg = "File is not tracked by git. Please add the file to git tracking first using 'git add <file>'"
            return False, error_msg

        # If there are other uncommitted changes, commit them
        commit_success, commit_message = await commit_changes(
            file_path,
            description="Snapshot before codemcp change",
            chat_id=chat_id,
        )

        if not commit_success:
            logging.debug(f"Failed to commit pending changes: {commit_message}")
        else:
            logging.debug(f"Pending changes status: {commit_message}")

    return True, None


def ensure_directory_exists(file_path: str) -> None:
    """Ensure the directory for the file exists, creating it if necessary.

    Args:
        file_path: The absolute path to the file

    """
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


async def async_open_text(
    file_path: str,
    mode: str = "r",
    encoding: str = "utf-8",
    errors: str = "replace",
) -> str:
    """Asynchronously open and read a text file.

    Args:
        file_path: The path to the file
        mode: The file open mode (default: 'r')
        encoding: The text encoding (default: 'utf-8')
        errors: How to handle encoding errors (default: 'replace')

    Returns:
        The file content as a string
    """
    async with await anyio.open_file(
        file_path, mode, encoding=encoding, errors=errors
    ) as f:
        return await f.read()


async def write_text_content(
    file_path: str,
    content: str,
    encoding: str = "utf-8",
    line_endings: str | None = None,
) -> None:
    """Write text content to a file with specified encoding and line endings.

    Args:
        file_path: The path to the file
        content: The content to write
        encoding: The encoding to use
        line_endings: The line endings to use ('CRLF', 'LF', '\r\n', or '\n').
                     If None, uses the system default.
    """
    # First normalize content to LF line endings
    normalized_content = normalize_to_lf(content)

    # Apply the requested line ending
    final_content = apply_line_endings(normalized_content, line_endings)

    # Ensure directory exists
    ensure_directory_exists(file_path)

    # Write the content asynchronously using run_in_executor
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, lambda: write_file_sync(file_path, final_content, encoding)
    )


def write_file_sync(file_path: str, content: str, encoding: str = "utf-8") -> None:
    """Synchronous helper function to write file content.

    Args:
        file_path: The path to the file
        content: The content to write
        encoding: The encoding to use
    """
    with open(file_path, "w", encoding=encoding) as f:
        f.write(content)
