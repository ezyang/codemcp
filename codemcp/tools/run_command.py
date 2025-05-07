#!/usr/bin/env python3

import shlex
from typing import Optional

from ..code_command import get_command_from_config, run_code_command
from ..common import normalize_file_path
from ..mcp import mcp
from .commit_utils import append_commit_hash

__all__ = [
    "run_command",
]


@mcp.tool()
async def run_command(
    project_dir: Optional[str] = None,
    command: str = "",
    arguments: Optional[str | list[str]] = None,
    chat_id: Optional[str] = None,
    commit_hash: Optional[str] = None,
    path: Optional[str] = None,
) -> str:
    """Run a command that is configured in codemcp.toml.

    Args:
        project_dir: The directory path containing the codemcp.toml file
        command: The type of command to run (e.g., "format", "lint", "test")
        arguments: Optional arguments to pass to the command. Can be a string or a list.
                  If a string, it will be parsed into a list of arguments using shell-style
                  tokenization (spaces separate arguments, quotes can be used for arguments
                  containing spaces, etc.). If a list, it will be used directly.
        chat_id: The unique ID of the current chat session
        commit_hash: Optional Git commit hash for version tracking
        path: Alias for project_dir parameter (for backward compatibility)

    Returns:
        A string containing the result of the command operation
    """
    # Use path as an alias for project_dir if project_dir is not provided
    effective_project_dir = project_dir if project_dir is not None else path
    if effective_project_dir is None:
        raise ValueError("Either project_dir or path must be provided")

    # Set default values
    chat_id = "" if chat_id is None else chat_id

    # Normalize the project directory path
    effective_project_dir = normalize_file_path(effective_project_dir)

    # Ensure arguments is a string for run_command
    args_str = (
        arguments
        if isinstance(arguments, str) or arguments is None
        else " ".join(arguments)
    )

    command_list = get_command_from_config(effective_project_dir, command)

    # If arguments are provided, extend the command with them
    if args_str and command_list:
        command_list = command_list.copy()
        parsed_args = shlex.split(args_str)
        command_list.extend(parsed_args)

    # Don't pass None to run_code_command
    actual_command = command_list if command_list is not None else []

    result = await run_code_command(
        effective_project_dir,
        command,
        actual_command,
        f"Auto-commit {command} changes",
        chat_id,
    )

    # Append commit hash
    result, _ = await append_commit_hash(result, effective_project_dir, commit_hash)
    return result
