#!/usr/bin/env python3

import shlex
from typing import Optional

from ..code_command import get_command_from_config, run_code_command

__all__ = [
    "run_command",
    "TOOL_NAME_FOR_PROMPT",
    "DESCRIPTION",
]

TOOL_NAME_FOR_PROMPT = "RunCommand"
DESCRIPTION = """
Runs a command.  This does NOT support arbitrary code execution, ONLY call
with this set of valid commands: format, lint, ghstack, test, accept
The arguments parameter should be a string and will be interpreted as space-separated
arguments using shell-style tokenization (spaces separate arguments, quotes can be used
for arguments containing spaces, etc.).


Command documentation:
- test: Accepts a pytest-style test selector as an argument to run a specific test.
- accept: Updates expecttest failing tests with their new values, akin to running with EXPECTTEST_ACCEPT=1. Accepts a pytest-style test selector as an argument to run a specific test.
"""


async def run_command(
    project_dir: str,
    command: str,
    arguments: Optional[str] = None,
    chat_id: str = None,
) -> str:
    """Run a command that is configured in codemcp.toml.

    Args:
        project_dir: The directory path containing the codemcp.toml file
        command: The type of command to run (e.g., "format", "lint", "test")
        arguments: Optional arguments to pass to the command as a string. It will be
                  parsed into a list of arguments using shell-style tokenization
                  (spaces separate arguments, quotes can be used for arguments
                  containing spaces, etc.)
        chat_id: The unique ID of the current chat session

    Returns:
        A string containing the result of the command operation
    """
    command_list = get_command_from_config(project_dir, command)

    # If arguments are provided, extend the command with them
    if arguments and command_list:
        command_list = command_list.copy()
        parsed_args = shlex.split(arguments)
        command_list.extend(parsed_args)

    return await run_code_command(
        project_dir, command, command_list, f"Auto-commit {command} changes", chat_id
    )
