#!/usr/bin/env python3

import logging
import os
import re
from pathlib import Path

from ..git_query import find_git_root
from ..rules import get_applicable_rules_content

__all__ = [
    "user_prompt",
    "is_slash_command",
    "resolve_slash_command",
    "get_command_content",
]


def is_slash_command(text: str) -> bool:
    """Check if the user's text starts with a slash command.

    Args:
        text: The user's text to check

    Returns:
        True if the text starts with a slash, False otherwise
    """
    return bool(text and text.strip().startswith("/"))


def resolve_slash_command(command: str) -> tuple[bool, str, str | None]:
    """Resolve a slash command to a file path.

    Args:
        command: The slash command (including the slash)

    Returns:
        A tuple of (success, command_name, file_path)
        If success is False, file_path will be None
    """
    # Strip the leading slash and any whitespace
    command = command.strip()[1:].strip()

    # Check for the command format: user:command-name
    match = re.match(r"^user:([a-zA-Z0-9_-]+)$", command)
    if not match:
        return False, command, None

    command_name = match.group(1)

    # Get the commands directory path
    commands_dir = Path.home() / ".claude" / "commands"

    # Create the commands directory if it doesn't exist
    os.makedirs(commands_dir, exist_ok=True)

    # Check if the command file exists
    command_file = commands_dir / f"{command_name}.md"
    if not command_file.exists():
        return False, command_name, None

    return True, command_name, str(command_file)


async def get_command_content(file_path: str) -> str:
    """Get the content of a command file.

    Args:
        file_path: The path to the command file

    Returns:
        The content of the command file
    """
    try:
        # Import here to avoid circular imports
        from ..file_utils import async_open_text

        # Read the file content
        content = await async_open_text(file_path)
        return content
    except Exception as e:
        logging.error(f"Error reading command file {file_path}: {e}")
        return f"Error reading command file: {e}"


async def user_prompt(user_text: str, chat_id: str | None = None) -> str:
    """Store the user's verbatim prompt text for later use.

    This function processes the user's prompt and applies any relevant cursor rules.
    If the user's prompt starts with a slash, it tries to resolve it as a command.

    Args:
        user_text: The user's original prompt verbatim
        chat_id: The unique ID of the current chat session

    Returns:
        A message with any applicable cursor rules or command content
    """
    logging.info(f"Received user prompt for chat ID {chat_id}: {user_text}")

    # Check if this is a slash command
    if is_slash_command(user_text):
        success, command_name, file_path = resolve_slash_command(user_text)
        if success and file_path:
            command_content = await get_command_content(file_path)
            logging.info(f"Resolved slash command {command_name} to file {file_path}")
            return command_content
        else:
            logging.info(f"Failed to resolve slash command {user_text}")
            return f"Unknown slash command: {command_name}"

    # Get the current working directory to find repo root
    cwd = os.getcwd()
    repo_root = find_git_root(cwd)

    result = "User prompt received"

    # If we're in a git repo, look for applicable rules
    if repo_root:
        # Add applicable rules (no file path for UserPrompt)
        result += get_applicable_rules_content(repo_root)

    return result
