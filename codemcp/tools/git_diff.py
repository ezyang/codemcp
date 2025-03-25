#!/usr/bin/env python3

import logging
import shlex
from typing import Any

from ..common import normalize_file_path
from ..git import is_git_repository
from ..shell import run_command

__all__ = [
    "git_diff",
    "render_result_for_assistant",
    "TOOL_NAME_FOR_PROMPT",
    "DESCRIPTION",
]

TOOL_NAME_FOR_PROMPT = "GitDiff"
DESCRIPTION = """
Shows differences between commits, commit and working tree, etc. using git diff.
This tool is read-only and safe to use with any arguments.
The arguments parameter should be a string and will be interpreted as space-separated
arguments using shell-style tokenization (spaces separate arguments, quotes can be used
for arguments containing spaces, etc.).

Example:
  git diff  # Show changes between working directory and index
  git diff HEAD~1  # Show changes between current commit and previous commit
  git diff branch1 branch2  # Show differences between two branches
  git diff --stat  # Show summary of changes instead of full diff
"""


async def git_diff(
    arguments: str | None = None,
    path: str | None = None,
    chat_id: str | None = None,
    signal=None,
) -> dict[str, Any]:
    """Execute git diff with the provided arguments.

    Args:
        arguments: Optional arguments to pass to git diff as a string
        path: The directory to execute the command in (must be in a git repository)
        chat_id: The unique ID of the current chat session
        signal: Optional abort signal to terminate the subprocess

    Returns:
        A dictionary with git diff output
    """

    if path is None:
        raise ValueError("Path must be provided for git diff")

    # Normalize the directory path
    absolute_path = normalize_file_path(path)

    # Verify this is a git repository
    if not await is_git_repository(absolute_path):
        raise ValueError(f"The provided path is not in a git repository: {path}")

    # Build command
    cmd = ["git", "diff"]

    # Add additional arguments if provided
    if arguments:
        parsed_args = shlex.split(arguments)
        cmd.extend(parsed_args)

    logging.debug(f"Executing git diff command: {' '.join(cmd)}")

    # Execute git diff command asynchronously
    result = await run_command(
        cmd=cmd,
        cwd=absolute_path,
        capture_output=True,
        text=True,
        check=True,  # Allow exception if git diff fails to propagate up
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
        output: The git diff output dictionary

    Returns:
        A formatted string representation of the results
    """
    return output.get("output", "")
