#!/usr/bin/env python3

import logging
import shlex
from typing import Any

from ..common import normalize_file_path
from ..git import is_git_repository
from ..shell import run_command

__all__ = [
    "git_blame",
    "render_result_for_assistant",
    "TOOL_NAME_FOR_PROMPT",
    "DESCRIPTION",
]

TOOL_NAME_FOR_PROMPT = "GitBlame"
DESCRIPTION = """
Shows what revision and author last modified each line of a file using git blame.
This tool is read-only and safe to use with any arguments.
The arguments parameter should be a string and will be interpreted as space-separated
arguments using shell-style tokenization (spaces separate arguments, quotes can be used
for arguments containing spaces, etc.).

Example:
  git blame path/to/file  # Show blame information for a file
  git blame -L 10,20 path/to/file  # Show blame information for lines 10-20
  git blame -w path/to/file  # Ignore whitespace changes
"""


async def git_blame(
    arguments: str | None = None,
    path: str | None = None,
    chat_id: str | None = None,
    signal=None,
) -> dict[str, Any]:
    """Execute git blame with the provided arguments.

    Args:
        arguments: Optional arguments to pass to git blame as a string
        path: The directory to execute the command in (must be in a git repository)
        chat_id: The unique ID of the current chat session
        signal: Optional abort signal to terminate the subprocess

    Returns:
        A dictionary with git blame output
    """

    if path is None:
        raise ValueError("Path must be provided for git blame")

    # Normalize the directory path
    absolute_path = normalize_file_path(path)

    # Verify this is a git repository
    if not await is_git_repository(absolute_path):
        raise ValueError(f"The provided path is not in a git repository: {path}")

    # Build command
    cmd = ["git", "blame"]

    # Add additional arguments if provided
    if arguments:
        parsed_args = shlex.split(arguments)
        cmd.extend(parsed_args)

    logging.debug(f"Executing git blame command: {' '.join(cmd)}")

    # Execute git blame command asynchronously
    result = await run_command(
        cmd=cmd,
        cwd=absolute_path,
        capture_output=True,
        text=True,
        check=True,  # Allow exception if git blame fails to propagate up
    )

    # Prepare output
    output = {
        "output": result.stdout,
    }

    # Add formatted result for assistant
    output["resultForAssistant"] = render_result_for_assistant(output)

    return output


def render_result_for_assistant(output: dict[str, Any]) -> str:
    """Render the results in a format suitable for the assistant.

    Args:
        output: The git blame output dictionary

    Returns:
        A formatted string representation of the results
    """
    return output.get("output", "")
