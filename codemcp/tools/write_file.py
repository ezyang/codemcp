#!/usr/bin/env python3

import json
import logging
import os
from typing import Any

from ..code_command import run_formatter_without_commit
from ..common import normalize_file_path
from ..file_utils import (
    check_file_path_and_permissions,
    check_git_tracking_for_existing_file,
    write_text_content,
)
from ..git import commit_changes
from ..line_endings import detect_line_endings, detect_repo_line_endings
from ..mcp import mcp
from .commit_utils import append_commit_hash

__all__ = [
    "write_file",
]


@mcp.tool()
async def write_file(
    path: str,
    content: str | dict[str, Any] | list[Any] | None = None,
    description: str | None = None,
    chat_id: str | None = None,
    commit_hash: str | None = None,
) -> str:
    """Write a file to the local filesystem. Overwrites the existing file if there is one.
    Provide a short description of the change.

    Before using this tool:

    1. Use the ReadFile tool to understand the file's contents and context

    2. Directory Verification (only applicable when creating new files):
       - Use the LS tool to verify the parent directory exists and is the correct location

    Args:
        path: The absolute path to the file to write
        content: The content to write to the file. Can be a string, dict, or list (will be converted to JSON)
        description: Short description of the change
        chat_id: The unique ID of the current chat session
        commit_hash: Optional Git commit hash for version tracking

    Returns:
        A success message

    Note:
        This function allows creating new files that don't exist yet.
        For existing files, it will reject attempts to write to files that are not tracked by git.
        Files must be tracked in the git repository before they can be modified.

    """
    # Set default values
    description = "" if description is None else description
    chat_id = "" if chat_id is None else chat_id

    # Normalize the file path
    path = normalize_file_path(path)

    # Normalize content - if content is not a string, serialize it to a string using json.dumps
    if content is not None and not isinstance(content, str):
        content_str = json.dumps(content)
    else:
        content_str = content or ""

    # Normalize newlines if content is a string
    # content_str could be dict/list that was passed directly from the content parameter

    content_str = (
        content_str.replace("\r\n", "\n")
        if isinstance(content_str, str)  # pyright: ignore[reportUnnecessaryIsInstance]
        else content_str
    )

    # Validate file path and permissions
    is_valid, error_message = await check_file_path_and_permissions(path)
    if not is_valid:
        raise ValueError(error_message)

    # Check git tracking for existing files
    is_tracked, track_error = await check_git_tracking_for_existing_file(path, chat_id)
    if not is_tracked:
        raise ValueError(track_error)

    # Determine line endings
    old_file_exists = os.path.exists(path)

    if old_file_exists:
        line_endings = await detect_line_endings(path)
    else:
        line_endings = detect_repo_line_endings(os.path.dirname(path))
        # Ensure directory exists for new files
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)

    # Write the content with UTF-8 encoding and proper line endings
    await write_text_content(path, content_str, "utf-8", line_endings)

    # Try to run the formatter on the file
    format_message = ""
    formatter_success, formatter_output = await run_formatter_without_commit(path)
    if formatter_success:
        logging.info(f"Auto-formatted {path}")
        if formatter_output.strip():
            format_message = f"\nAuto-formatted the file"
    else:
        # Only log warning if there was actually a format command configured but it failed
        if not "No format command configured" in formatter_output:
            logging.warning(f"Failed to auto-format {path}: {formatter_output}")

    # Commit the changes
    git_message = ""
    success, message = await commit_changes(path, description, chat_id)
    if success:
        git_message = f"\nChanges committed to git: {description}"
    else:
        git_message = f"\nFailed to commit changes to git: {message}"

    result = f"Successfully wrote to {path}{format_message}{git_message}"

    # Append commit hash
    result, _ = await append_commit_hash(result, path, commit_hash)
    return result
