#!/usr/bin/env python3

import shlex
from typing import Optional

from mcp.server.fastmcp import Context

from ..code_command import get_command_from_config, run_code_command
from ..main import get_chat_id_from_context, mcp

__all__ = [
    "run_command",
    "run_command_tool",
]


async def run_command(
    project_dir: str,
    command: str,
    arguments: Optional[str] = None,
    chat_id: str = "",
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

    # Don't pass None to run_code_command
    actual_command = command_list if command_list is not None else []

    return await run_code_command(
        project_dir, command, actual_command, f"Auto-commit {command} changes", chat_id
    )


@mcp.tool()
async def run_command_tool(
    ctx: Context, path: str, command: str, arguments: Optional[str] = None
) -> str:
    """Runs a command. This does NOT support arbitrary code execution, ONLY call
    with this set of valid commands: format, lint, ghstack, typecheck, test, accept
    The arguments parameter should be a string and will be interpreted as space-separated
    arguments using shell-style tokenization (spaces separate arguments, quotes can be used
    for arguments containing spaces, etc.).

    Command documentation:
    - test: Accepts a pytest-style test selector as an argument to run a specific test.
    - accept: Updates expecttest failing tests with their new values, akin to running with EXPECTTEST_ACCEPT=1.
      Accepts a pytest-style test selector as an argument to run a specific test.
    """
    # Get chat ID from context
    chat_id = get_chat_id_from_context(ctx)
    return await run_command(path, command, arguments, chat_id)
