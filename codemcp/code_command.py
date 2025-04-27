#!/usr/bin/env python3

import logging
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple, cast

import tomli

from .common import normalize_file_path, truncate_output_content
from .file_utils import async_open_text
from .git import commit_changes, get_repository_root, is_git_repository
from .shell import run_command

__all__ = [
    "get_command_from_config",
    "check_for_changes",
    "run_code_command",
    "run_formatter_without_commit",
]


def get_command_from_config(project_dir: str, command_name: str) -> Optional[List[str]]:
    """Get a command from the codemcp.toml file.

    Args:
        project_dir: The directory path containing the codemcp.toml file
        command_name: The name of the command to retrieve (e.g., "lint", "format")

    Returns:
        A list of command parts if configured, None otherwise
    """
    try:
        full_dir_path = normalize_file_path(project_dir)
        config_path = os.path.join(full_dir_path, "codemcp.toml")

        if not os.path.exists(config_path):
            logging.warning(f"Config file not found: {config_path}")
            return None

        with open(config_path, "rb") as f:
            config: Dict[str, Any] = tomli.load(f)

        if "commands" in config and command_name in config["commands"]:
            cmd_config = config["commands"][command_name]
            # Handle both direct command lists and dictionaries with 'command' field
            if isinstance(cmd_config, list):
                return cast(List[str], cmd_config)
            elif isinstance(cmd_config, dict) and "command" in cmd_config:
                return cast(List[str], cmd_config["command"])

        return None
    except Exception as e:
        logging.error(f"Error loading {command_name} command: {e}")
        return None


async def check_for_changes(project_dir: str) -> bool:
    """Check if an operation made any changes to the code.

    Args:
        project_dir: The directory path to check

    Returns:
        True if changes were detected, False otherwise
    """
    try:
        # Get the git repository root for reliable status checking
        try:
            git_cwd = await get_repository_root(project_dir)
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            logging.error(f"Error getting git repository root: {e}")
            # Fall back to the project directory
            git_cwd = project_dir

        # Check if working directory has uncommitted changes
        status_result = await run_command(
            ["git", "status", "--porcelain"],
            cwd=git_cwd,
            check=True,
            capture_output=True,
            text=True,
        )

        # If status output is not empty, there are changes
        return bool(status_result.stdout.strip())
    except Exception as e:
        logging.error(f"Error checking for git changes: {e}")
        return False


async def run_code_command(
    project_dir: str,
    command_name: str,
    command: List[str],
    commit_message: str,
    chat_id: Optional[str] = None,
) -> str:
    """Run a code command (lint, format, etc.) and handle git operations.

    Args:
        project_dir: The directory path containing the code to process
        command_name: The name of the command for logging and messages (e.g., "lint", "format")
        command: The command to run
        commit_message: The commit message to use if changes are made
        chat_id: The unique ID of the current chat session

    Returns:
        A string containing the result of the operation
    """
    try:
        full_dir_path = normalize_file_path(project_dir)

        if not os.path.exists(full_dir_path):
            raise FileNotFoundError(f"Directory does not exist: {project_dir}")

        if not os.path.isdir(full_dir_path):
            raise NotADirectoryError(f"Path is not a directory: {project_dir}")

        if not command:
            # Map the command_name to keep backward compatibility with existing tests
            command_key = command_name
            if command_name == "linting":
                command_key = "lint"
            elif command_name == "formatting":
                command_key = "format"

            raise ValueError(f"No {command_key} command configured in codemcp.toml")

        # Check if directory is in a git repository
        is_git_repo = await is_git_repository(full_dir_path)

        # If it's a git repo, commit any pending changes before running the command
        if is_git_repo:
            logging.info(f"Committing any pending changes before {command_name}")
            chat_id_str = str(chat_id) if chat_id is not None else ""
            commit_result = await commit_changes(
                full_dir_path,
                f"Snapshot before auto-{command_name}",
                chat_id_str,
                commit_all=True,
            )
            if not commit_result[0]:
                logging.warning(f"Failed to commit pending changes: {commit_result[1]}")

        # Run the command
        try:
            result = await run_command(
                command,
                cwd=full_dir_path,
                check=True,
                capture_output=True,
                text=True,
            )

            # Additional logging is already done by run_command

            # Truncate the output if needed, prioritizing the end content
            truncated_stdout = truncate_output_content(result.stdout, prefer_end=True)

            # If it's a git repo, commit any changes made by the command
            if is_git_repo:
                has_changes = await check_for_changes(full_dir_path)
                if has_changes:
                    logging.info(f"Changes detected after {command_name}, committing")
                    chat_id_str = str(chat_id) if chat_id is not None else ""
                    success, commit_result_message = await commit_changes(
                        full_dir_path, commit_message, chat_id_str, commit_all=True
                    )

                    if success:
                        return f"Code {command_name} successful and changes committed:\n{truncated_stdout}"
                    else:
                        logging.warning(
                            f"Failed to commit {command_name} changes: {commit_result_message}"
                        )
                        return f"Code {command_name} successful but failed to commit changes:\n{truncated_stdout}\nCommit error: {commit_result_message}"

            return f"Code {command_name} successful:\n{truncated_stdout}"
        except subprocess.CalledProcessError as e:
            # Map the command_name to keep backward compatibility with existing tests
            command_key = command_name.title()
            if command_name == "linting":
                command_key = "Lint"
            elif command_name == "formatting":
                command_key = "Format"

            # Truncate stdout and stderr if needed, prioritizing the end content
            truncated_stdout = truncate_output_content(
                e.output if e.output else "", prefer_end=True
            )
            truncated_stderr = truncate_output_content(
                e.stderr if e.stderr else "", prefer_end=True
            )

            # Include both stdout and stderr in the error message
            stdout_info = (
                f"STDOUT:\n{truncated_stdout}"
                if truncated_stdout
                else "STDOUT: <empty>"
            )
            stderr_info = (
                f"STDERR:\n{truncated_stderr}"
                if truncated_stderr
                else "STDERR: <empty>"
            )
            error_msg = f"{command_key} command failed with exit code {e.returncode}:\n{stdout_info}\n{stderr_info}"

            # Note: run_command already logs the command and stderr at debug level
            # We just need to log the error summary at error level
            logging.error(
                f"{command_name.title()} command failed with exit code {e.returncode}"
            )
            return f"Error: {error_msg}"

    except Exception as e:
        error_msg = f"Error during {command_name}: {e}"
        logging.error(error_msg)
        return f"Error: {error_msg}"


async def run_formatter_without_commit(file_path: str) -> Tuple[bool, str, str]:
    """Run the formatter on a specific file without performing pre/post commit operations.

    Args:
        file_path: Absolute path to the file to format

    Returns:
        A tuple containing (success_status, message, post_format_content)
        The post_format_content will be an empty string if formatting failed

    Raises:
        Propagates any unexpected errors during formatting
    """
    # Get the project directory (repository root)
    project_dir = await get_repository_root(file_path)

    # Get the format command from config - this is the only expected failure mode
    format_command = get_command_from_config(project_dir, "format")
    if not format_command:
        return False, "No format command configured in codemcp.toml", ""

    # Use relative path from project_dir for the formatting command
    rel_path = os.path.relpath(file_path, project_dir)

    # Run the formatter with the specific file path
    command = format_command + [rel_path]
    result = await run_command(
        command,
        cwd=project_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    # Read the file after formatting to get the current content
    post_format_content = ""
    if os.path.exists(file_path):
        try:
            post_format_content = await async_open_text(file_path, encoding="utf-8")
        except Exception as e:
            logging.warning(f"Failed to read formatted file: {e}")

    # If we get here, the formatter ran successfully
    truncated_stdout = truncate_output_content(result.stdout, prefer_end=True)
    return (
        True,
        f"File formatted successfully:\n{truncated_stdout}",
        post_format_content,
    )
