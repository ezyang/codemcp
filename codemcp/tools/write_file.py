#!/usr/bin/env python3

import logging
import os

from mcp.server.fastmcp import Context

from ..code_command import run_formatter_without_commit
from ..file_utils import (
    check_file_path_and_permissions,
    check_git_tracking_for_existing_file,
    write_text_content,
)
from ..git import commit_changes
from ..line_endings import detect_line_endings, detect_repo_line_endings
from ..main import get_chat_id_from_context, mcp

__all__ = [
    "write_file_content",
    "write_file",
]


async def write_file_content(
    file_path: str, content: str, description: str = "", chat_id: str = ""
) -> str:
    """Write content to a file.

    Args:
        file_path: The absolute path to the file to write
        content: The content to write to the file
        description: Short description of the change
        chat_id: The unique ID of the current chat session

    Returns:
        A success message

    Note:
        This function allows creating new files that don't exist yet.
        For existing files, it will reject attempts to write to files that are not tracked by git.
        Files must be tracked in the git repository before they can be modified.

    """
    # Validate file path and permissions
    is_valid, error_message = await check_file_path_and_permissions(file_path)
    if not is_valid:
        raise ValueError(error_message)

    # Check git tracking for existing files
    is_tracked, track_error = await check_git_tracking_for_existing_file(
        file_path, chat_id
    )
    if not is_tracked:
        raise ValueError(track_error)

    # Determine line endings
    old_file_exists = os.path.exists(file_path)

    if old_file_exists:
        line_endings = await detect_line_endings(file_path)
    else:
        line_endings = detect_repo_line_endings(os.path.dirname(file_path))
        # Ensure directory exists for new files
        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)

    # Write the content with UTF-8 encoding and proper line endings
    await write_text_content(file_path, content, "utf-8", line_endings)

    # Try to run the formatter on the file
    format_message = ""
    formatter_success, formatter_output = await run_formatter_without_commit(file_path)
    if formatter_success:
        logging.info(f"Auto-formatted {file_path}")
        if formatter_output.strip():
            format_message = f"\nAuto-formatted the file"
    else:
        # Only log warning if there was actually a format command configured but it failed
        if not "No format command configured" in formatter_output:
            logging.warning(f"Failed to auto-format {file_path}: {formatter_output}")

    # Commit the changes
    git_message = ""
    success, message = await commit_changes(file_path, description, chat_id)
    if success:
        git_message = f"\nChanges committed to git: {description}"
    else:
        git_message = f"\nFailed to commit changes to git: {message}"

    return f"Successfully wrote to {file_path}{format_message}{git_message}"


@mcp.tool()
async def write_file(
    ctx: Context, file_path: str, content: str, description: str
) -> str:
    """Write a file to the local filesystem. Overwrites the existing file if there is one.
    Provide a short description of the change.

    Before using this tool:

    1. Use the ReadFile tool to understand the file's contents and context

    2. Directory Verification (only applicable when creating new files):
       - Use the LS tool to verify the parent directory exists and is the correct location
    """
    # Get chat ID from context
    chat_id = get_chat_id_from_context(ctx)
    return await write_file_content(file_path, content, description, chat_id)
