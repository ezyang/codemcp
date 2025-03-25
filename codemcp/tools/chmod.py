#!/usr/bin/env python3

import logging
import os
import stat
from typing import Any, Literal

from ..common import normalize_file_path
from ..git import commit_changes
from ..shell import run_command

__all__ = [
    "chmod",
    "render_result_for_assistant",
    "TOOL_NAME_FOR_PROMPT",
    "DESCRIPTION",
]

TOOL_NAME_FOR_PROMPT = "Chmod"
DESCRIPTION = """
Changes file permissions using chmod. Unlike standard chmod, this tool only supports 
a+x (add executable permission) and a-x (remove executable permission), because these 
are the only bits that git knows how to track.

Example:
  chmod a+x path/to/file  # Makes a file executable by all users
  chmod a-x path/to/file  # Makes a file non-executable for all users
"""


async def chmod(
    path: str,
    mode: Literal["a+x", "a-x"],
    chat_id: str | None = None,
    signal=None,
) -> dict[str, Any]:
    """Change file permissions using chmod.

    Args:
        path: The absolute path to the file to modify
        mode: The chmod mode to apply, only "a+x" and "a-x" are supported
        chat_id: The unique ID of the current chat session
        signal: Optional abort signal to terminate the subprocess

    Returns:
        A dictionary with chmod output
    """
    if not path:
        raise ValueError("File path must be provided")

    # Normalize the file path
    absolute_path = normalize_file_path(path)

    # Check if file exists
    if not os.path.exists(absolute_path):
        raise FileNotFoundError(f"The file does not exist: {path}")

    # Verify that the mode is supported
    if mode not in ["a+x", "a-x"]:
        raise ValueError(
            f"Unsupported chmod mode: {mode}. Only 'a+x' and 'a-x' are supported."
        )

    # Get the directory containing the file for git operations
    directory = os.path.dirname(absolute_path)

    # Check current file permissions
    current_mode = os.stat(absolute_path).st_mode
    is_executable = bool(current_mode & stat.S_IXUSR)

    if mode == "a+x" and is_executable:
        message = f"File '{path}' is already executable"
        return {
            "output": message,
            "resultForAssistant": message,
        }
    elif mode == "a-x" and not is_executable:
        message = f"File '{path}' is already non-executable"
        return {
            "output": message,
            "resultForAssistant": message,
        }

    # Execute chmod command
    cmd = ["chmod", mode, absolute_path]
    await run_command(
        cmd=cmd,
        cwd=directory,
        capture_output=True,
        text=True,
        check=True,
    )

    # Prepare success message
    if mode == "a+x":
        description = f"Make '{os.path.basename(absolute_path)}' executable"
        action_msg = f"Made file '{path}' executable"
    else:
        description = (
            f"Remove executable permission from '{os.path.basename(absolute_path)}'"
        )
        action_msg = f"Removed executable permission from file '{path}'"

    # Commit the changes
    success, commit_message = await commit_changes(
        directory,
        description,
        chat_id,
    )

    if not success:
        raise RuntimeError(f"Failed to commit chmod changes: {commit_message}")

    # Prepare output
    output = {
        "output": f"{action_msg} and committed changes",
    }

    # Add formatted result for assistant
    output["resultForAssistant"] = render_result_for_assistant(output)

    return output


def render_result_for_assistant(output: dict[str, Any]) -> str:
    """Render the results in a format suitable for the assistant.

    Args:
        output: The chmod output dictionary

    Returns:
        A formatted string representation of the results
    """
    return output.get("output", "")
